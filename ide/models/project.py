import re
import uuid
import json

from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError

from ide.models.files import ResourceFile, ResourceIdentifier, SourceFile, ResourceVariant
from ide.models.dependency import Dependency
from ide.models.meta import IdeModel
from ide.utils import generate_half_uuid
from ide.utils.version import version_to_semver, semver_to_version, parse_sdk_version

__author__ = 'katharine'


def version_validator(value):
    try:
        parse_sdk_version(value)
    except ValueError:
        raise ValidationError(_("Invalid version string. Versions should be major[.minor]."))


class Project(IdeModel):
    owner = models.ForeignKey(User)
    name = models.CharField(max_length=50)
    last_modified = models.DateTimeField(auto_now_add=True)

    PROJECT_TYPES = (
        ('native', _('Pebble C SDK')),
        ('simplyjs', _('Simply.js')),
        ('pebblejs', _('Pebble.js (beta)')),
        ('package', _('Pebble Package')),
    )
    project_type = models.CharField(max_length=10, choices=PROJECT_TYPES, default='native')

    SDK_VERSIONS = (
        ('2', _('SDK 2 (Pebble, Pebble Steel)')),
        ('3', _('SDK 3 beta (Pebble Time)')),
    )
    sdk_version = models.CharField(max_length=6, choices=SDK_VERSIONS, default='2')

    # New settings for 2.0
    app_uuid = models.CharField(max_length=36, blank=True, null=True, default=generate_half_uuid)
    app_company_name = models.CharField(max_length=100, blank=True, null=True)
    app_short_name = models.CharField(max_length=100, blank=True, null=True)
    app_long_name = models.CharField(max_length=100, blank=True, null=True)
    app_version_label = models.CharField(max_length=40, blank=True, null=True, default='1.0', validators=[version_validator])
    app_is_watchface = models.BooleanField(default=False)
    app_is_hidden = models.BooleanField(default=False)
    app_is_shown_on_communication = models.BooleanField(default=False)
    app_capabilities = models.CharField(max_length=255, blank=True, null=True)
    app_keys = models.TextField(default="{}")
    app_jshint = models.BooleanField(default=True)
    app_platforms = models.TextField(max_length=255, blank=True, null=True)
    app_modern_multi_js = models.BooleanField(default=True)
    app_keywords = models.TextField(default='[]')

    app_capability_list = property(lambda self: self.app_capabilities.split(','))
    app_platform_list = property(lambda self: self.app_platforms.split(',') if self.app_platforms else [])

    OPTIMISATION_CHOICES = (
        ('0', 'None'),
        ('1', 'Limited'),
        ('s', 'Prefer smaller'),
        ('2', 'Prefer faster'),
        ('3', 'Aggressive (faster, bigger)'),
    )

    optimisation = models.CharField(max_length=1, choices=OPTIMISATION_CHOICES, default='s')

    github_repo = models.CharField(max_length=100, blank=True, null=True)
    github_branch = models.CharField(max_length=100, blank=True, null=True)
    github_last_sync = models.DateTimeField(blank=True, null=True)
    github_last_commit = models.CharField(max_length=40, blank=True, null=True)
    github_hook_uuid = models.CharField(max_length=36, blank=True, null=True)
    github_hook_build = models.BooleanField(default=False)

    def set_dependencies(self, dependencies):
        """ Set the project's dependencies from a dictionary.
        :param dependencies: A dictionary of dependency->version
        """
        with transaction.atomic():
            Dependency.objects.filter(project=self).delete()
            for name, version in dependencies.iteritems():
                dep = Dependency.objects.create(project=self, name=name, version=version)
                dep.full_clean()
                dep.save()

    @property
    def keywords(self):
        """ Get the project's keywords as a list of strings """
        return json.loads(self.app_keywords)

    @keywords.setter
    def keywords(self, value):
        """ Set the project's keywords from a list of strings """
        self.app_keywords = json.dumps(value)

    def get_dependencies(self):
        """ Get the project's dependencies as a dictionary
        :return: A dictinoary of dependency->version
        """
        return {d.name: d.version for d in self.dependencies.all()}

    @property
    def uses_array_message_keys(self):
        return isinstance(json.loads(self.app_keys), list)

    def get_parsed_appkeys(self):
        """ Get the project's app keys, or raise an error of any are invalid.
        :return: A list of (appkey, value) tuples, where value is either a length or a size, depending on the kind of appkey.
        """
        app_keys = json.loads(self.app_keys)
        if isinstance(app_keys, dict):
            return sorted(app_keys.iteritems(), key=lambda x: x[1])
        else:
            parsed_keys = []
            for appkey in app_keys:
                parsed = re.match(r'^([a-zA-Z_][_a-zA-Z\d]*)(?:\[(\d+)\])?$', appkey)
                if not parsed:
                    raise ValueError("Bad Appkey %s" % appkey)
                parsed_keys.append((parsed.group(1), parsed.group(2) or 1))
            return parsed_keys

    def get_last_build(self):
        try:
            return self.builds.order_by('-id')[0]
        except IndexError:
            return None

    def get_menu_icon(self):
        try:
            return self.resources.filter(is_menu_icon=True)[0]
        except IndexError:
            return None

    def has_platform(self, platform):
        return self.app_platforms is None or platform in self.app_platform_list

    @property
    def semver(self):
        """ Get the app's version label formatted as a semver """
        return version_to_semver(self.app_version_label)

    @semver.setter
    def semver(self, value):
        """ Set the app's version label from a semver string"""
        self.app_version_label = semver_to_version(value)

    @property
    def supported_platforms(self):
        supported_platforms = ["aplite", "basalt"]
        if self.sdk_version != '2':
            supported_platforms.append("chalk")
        return supported_platforms

    @property
    def is_native_or_package(self):
        return self.project_type in {'native', 'package'}

    def clean(self):
        is_sdk_2 = self.sdk_version == "2"
        is_package = self.project_type == 'package'
        if is_sdk_2 and self.uses_array_message_keys:
            raise ValidationError(_("SDK2 appKeys must be an object, not a list."))
        if is_package:
            if is_sdk_2:
                raise ValidationError(_("Packages are not available for SDK 2"))
            if not self.uses_array_message_keys:
                raise ValidationError(_("Packages must use array based appmessage keys"))
            if not self.app_modern_multi_js:
                raise ValidationError(_("Packages must use CommonJS-style JS Handling."))

    last_build = property(get_last_build)
    menu_icon = property(get_menu_icon)

    def __unicode__(self):
        return u"%s" % self.name


class TemplateProject(Project):
    KIND_TEMPLATE = 1
    KIND_SDK_DEMO = 2
    KIND_CHOICES = (
        (KIND_TEMPLATE, _('Template')),
        (KIND_SDK_DEMO, _('SDK Demo')),
    )

    template_kind = models.IntegerField(choices=KIND_CHOICES, db_index=True)

    def copy_into_project(self, project):
        uuid_string = ", ".join(["0x%02X" % ord(b) for b in uuid.uuid4().bytes])
        for resource in self.resources.all():
            new_resource = ResourceFile.objects.create(project=project, file_name=resource.file_name, kind=resource.kind)
            for variant in resource.variants.all():
                new_variant = ResourceVariant.objects.create(resource_file=new_resource, tags=variant.tags)
                new_variant.save_string(variant.get_contents())
            for i in resource.identifiers.all():
                ResourceIdentifier.objects.create(
                    resource_file=new_resource,
                    resource_id=i.resource_id,
                    character_regex=i.character_regex,
                    tracking=i.tracking,
                    compatability=i.compatibility,
                    target_platforms=i.target_platforms,
                    memory_format=i.memory_format,
                    storage_format=i.storage_format,
                    space_optmization=i.space_optimisation
                )

        for source_file in self.source_files.all():
            new_file = SourceFile.objects.create(project=project, file_name=source_file.file_name)
            new_file.save_file(source_file.get_contents().replace("__UUID_GOES_HERE__", uuid_string))

        # Copy over relevant project properties.
        # NOTE: If new, relevant properties are added, they must be copied here.
        # todo: can we do better than that? Maybe we could reuse the zip import mechanism or something...
        project.app_capabilities = self.app_capabilities
        project.app_is_watchface = self.app_is_watchface
        project.app_is_hidden = self.app_is_hidden
        project.app_is_shown_on_communication = self.app_is_shown_on_communication
        project.app_keys = self.app_keys
        project.app_jshint = self.app_jshint
        project.app_modern_multi_js = self.app_modern_multi_js
        project.save()
