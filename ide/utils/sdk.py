import json
import re
from django.utils.translation import ugettext as _
from ide.utils.project import APPINFO_MANIFEST, PACKAGE_MANIFEST, InvalidProjectArchiveException

__author__ = 'katharine'


def generate_wscript_file_sdk2(project, for_export=False):
    jshint = project.app_jshint
    wscript = """
#
# This file is the default set of rules to compile a Pebble project.
#
# Feel free to customize this to your needs.
#

import os.path
try:
    from sh import CommandNotFound, jshint, cat, ErrorReturnCode_2
    hint = jshint
except (ImportError, CommandNotFound):
    hint = None

top = '.'
out = 'build'

def options(ctx):
    ctx.load('pebble_sdk')

def configure(ctx):
    ctx.load('pebble_sdk')
    global hint
    if hint is not None:
        hint = hint.bake(['--config', 'pebble-jshintrc'])

def build(ctx):
    if {{jshint}} and hint is not None:
        try:
            hint([node.abspath() for node in ctx.path.ant_glob("src/**/*.js")], _tty_out=False) # no tty because there are none in the cloudpebble sandbox.
        except ErrorReturnCode_2 as e:
            ctx.fatal("\\nJavaScript linting failed (you can disable this in Project Settings):\\n" + e.stdout)

    # Concatenate all our JS files (but not recursively), and only if any JS exists in the first place.
    ctx.path.make_node('src/js/').mkdir()
    js_paths = ctx.path.ant_glob(['src/*.js', 'src/**/*.js'])
    if js_paths:
        ctx(rule='cat ${SRC} > ${TGT}', source=js_paths, target='pebble-js-app.js')
        has_js = True
    else:
        has_js = False

    ctx.load('pebble_sdk')

    ctx.pbl_program(source=ctx.path.ant_glob('src/**/*.c'),
                    target='pebble-app.elf')

    if os.path.exists('worker_src'):
        ctx.pbl_worker(source=ctx.path.ant_glob('worker_src/**/*.c'),
                        target='pebble-worker.elf')
        ctx.pbl_bundle(elf='pebble-app.elf',
                        worker_elf='pebble-worker.elf',
                        js='pebble-js-app.js' if has_js else [])
    else:
        ctx.pbl_bundle(elf='pebble-app.elf',
                       js='pebble-js-app.js' if has_js else [])

"""
    return wscript.replace('{{jshint}}', 'True' if jshint and not for_export else 'False')


def generate_wscript_file_package(project, for_export):
    jshint = project.app_jshint
    wscript = """
#
# This file is the default set of rules to compile a Pebble project.
#
# Feel free to customize this to your needs.
#
import os
import shutil
import waflib

try:
    from sh import CommandNotFound, jshint, cat, ErrorReturnCode_2
    hint = jshint
except (ImportError, CommandNotFound):
    hint = None

top = '.'
out = 'build'


def distclean(ctx):
    if os.path.exists('dist.zip'):
        os.remove('dist.zip')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    waflib.Scripting.distclean(ctx)


def options(ctx):
    ctx.load('pebble_sdk_lib')


def configure(ctx):
    ctx.load('pebble_sdk_lib')


def build(ctx):
    if {{jshint}} and hint is not None:
        try:
            hint([node.abspath() for node in ctx.path.ant_glob("src/**/*.js")], _tty_out=False) # no tty because there are none in the cloudpebble sandbox.
        except ErrorReturnCode_2 as e:
            ctx.fatal("\\nJavaScript linting failed (you can disable this in Project Settings):\\n" + e.stdout)

    ctx.load('pebble_sdk_lib')

    cached_env = ctx.env
    for platform in ctx.env.TARGET_PLATFORMS:
        ctx.env = ctx.all_envs[platform]
        ctx.set_group(ctx.env.PLATFORM_NAME)
        lib_name = '{}/{}'.format(ctx.env.BUILD_DIR, ctx.env.PROJECT_INFO['name'])
        ctx.pbl_build(source=ctx.path.ant_glob('src/c/**/*.c'), target=lib_name, bin_type='lib')
    ctx.env = cached_env

    ctx.set_group('bundle')
    ctx.pbl_bundle(includes=ctx.path.ant_glob('include/**/*.h'),
                   js=ctx.path.ant_glob(['src/js/**/*.js', 'src/js/**/*.json']),
                   bin_type='lib')

    if ctx.cmd == 'clean':
        for n in ctx.path.ant_glob(['dist/**/*', 'dist.zip'], quiet=True):
            n.delete()
"""
    return wscript.replace('{{jshint}}', 'True' if jshint and not for_export else 'False')


def generate_wscript_file_sdk3(project, for_export):
    jshint = project.app_jshint
    if not project.app_modern_multi_js:
        wscript = """
    #
# This file is the default set of rules to compile a Pebble project.
#
# Feel free to customize this to your needs.
#

import os.path
try:
    from sh import CommandNotFound, jshint, cat, ErrorReturnCode_2
    hint = jshint
except (ImportError, CommandNotFound):
    hint = None

top = '.'
out = 'build'

def options(ctx):
    ctx.load('pebble_sdk')

def configure(ctx):
    ctx.load('pebble_sdk')

def build(ctx):
    if {{jshint}} and hint is not None:
        try:
            hint([node.abspath() for node in ctx.path.ant_glob("src/**/*.js")], _tty_out=False) # no tty because there are none in the cloudpebble sandbox.
        except ErrorReturnCode_2 as e:
            ctx.fatal("\\nJavaScript linting failed (you can disable this in Project Settings):\\n" + e.stdout)

    # Concatenate all our JS files (but not recursively), and only if any JS exists in the first place.
    ctx.path.make_node('src/js/').mkdir()
    js_paths = ctx.path.ant_glob(['src/*.js', 'src/**/*.js'])
    if js_paths:
        ctx(rule='cat ${SRC} > ${TGT}', source=js_paths, target='pebble-js-app.js')
        has_js = True
    else:
        has_js = False

    ctx.load('pebble_sdk')

    build_worker = os.path.exists('worker_src')
    binaries = []

    for p in ctx.env.TARGET_PLATFORMS:
        ctx.set_env(ctx.all_envs[p])
        ctx.set_group(ctx.env.PLATFORM_NAME)
        app_elf='{}/pebble-app.elf'.format(p)
        ctx.pbl_program(source=ctx.path.ant_glob('src/**/*.c'),
        target=app_elf)

        if build_worker:
            worker_elf='{}/pebble-worker.elf'.format(p)
            binaries.append({'platform': p, 'app_elf': app_elf, 'worker_elf': worker_elf})
            ctx.pbl_worker(source=ctx.path.ant_glob('worker_src/**/*.c'),
            target=worker_elf)
        else:
            binaries.append({'platform': p, 'app_elf': app_elf})

    ctx.set_group('bundle')
    ctx.pbl_bundle(binaries=binaries, js='pebble-js-app.js' if has_js else [])
    """
    else:
        wscript = """#
# This file is the default set of rules to compile a Pebble project.
#
# Feel free to customize this to your needs.
#

import os.path

top = '.'
out = 'build'


def options(ctx):
    ctx.load('pebble_sdk')


def configure(ctx):
    ctx.load('pebble_sdk')


def build(ctx):
    ctx.load('pebble_sdk')

    build_worker = os.path.exists('worker_src')
    binaries = []

    for p in ctx.env.TARGET_PLATFORMS:
        ctx.set_env(ctx.all_envs[p])
        ctx.set_group(ctx.env.PLATFORM_NAME)
        app_elf = '{}/pebble-app.elf'.format(ctx.env.BUILD_DIR)
        ctx.pbl_program(source=ctx.path.ant_glob('src/**/*.c'), target=app_elf)

        if build_worker:
            worker_elf = '{}/pebble-worker.elf'.format(ctx.env.BUILD_DIR)
            binaries.append({'platform': p, 'app_elf': app_elf, 'worker_elf': worker_elf})
            ctx.pbl_worker(source=ctx.path.ant_glob('worker_src/**/*.c'), target=worker_elf)
        else:
            binaries.append({'platform': p, 'app_elf': app_elf})

    ctx.set_group('bundle')
    ctx.pbl_bundle(binaries=binaries, js=ctx.path.ant_glob('src/js/**/*.js'), js_entry_file='src/js/app.js')
"""

    return wscript.replace('{{jshint}}', 'True' if jshint and not for_export else 'False')


def generate_wscript_file(project, for_export=False):
    if project.project_type == 'package':
        return generate_wscript_file_package(project, for_export)
    if project.sdk_version == '2':
        return generate_wscript_file_sdk2(project, for_export)
    elif project.sdk_version == '3':
        return generate_wscript_file_sdk3(project, for_export)


def generate_jshint_file(project):
    return """
/*
 * Example jshint configuration file for Pebble development.
 *
 * Check out the full documentation at http://www.jshint.com/docs/options/
 */
{
  // Declares the existence of the globals available in PebbleKit JS.
  "globals": {
    "Pebble": true,
    "console": true,
    "WebSocket": true,
    "XMLHttpRequest": true,
    "navigator": true, // For navigator.geolocation
    "localStorage": true,
    "setTimeout": true,
    "setInterval": true,
    "Int8Array": true,
    "Uint8Array": true,
    "Uint8ClampedArray": true,
    "Int16Array": true,
    "Uint16Array": true,
    "Int32Array": true,
    "Uint32Array": true,
    "Float32Array": true,
    "Float64Array": true
  },

  // Do not mess with standard JavaScript objects (Array, Date, etc)
  "freeze": true,

  // Do not use eval! Keep this warning turned on (ie: false)
  "evil": false,

  /*
   * The options below are more style/developer dependent.
   * Customize to your liking.
   */

  // All variables should be in camelcase - too specific for CloudPebble builds to fail
  // "camelcase": true,

  // Do not allow blocks without { } - too specific for CloudPebble builds to fail.
  // "curly": true,

  // Prohibits the use of immediate function invocations without wrapping them in parentheses
  "immed": true,

  // Don't enforce indentation, because it's not worth failing builds over
  // (especially given our somewhat lacklustre support for it)
  "indent": false,

  // Do not use a variable before it's defined
  "latedef": "nofunc",

  // Spot undefined variables
  "undef": "true",

  // Spot unused variables
  "unused": "true"
}
"""


def manifest_name_for_project(project):
    if project.is_native_or_package and project.sdk_version == '3':
        return PACKAGE_MANIFEST
    else:
        return APPINFO_MANIFEST


def generate_manifest(project, resources):
    if project.is_native_or_package:
        if project.sdk_version == '2':
            return generate_v2_manifest(project, resources)
        else:
            return generate_v3_manifest(project, resources)
    elif project.project_type == 'pebblejs':
        return generate_pebblejs_manifest(project, resources)
    elif project.project_type == 'simplyjs':
        return generate_simplyjs_manifest(project)
    else:
        raise Exception(_("Unknown project type %s") % project.project_type)


def generate_v2_manifest(project, resources):
    return dict_to_pretty_json(generate_v2_manifest_dict(project, resources))


def generate_v3_manifest(project, resources):
    return dict_to_pretty_json(generate_v3_manifest_dict(project, resources))


def generate_v2_manifest_dict(project, resources):
    manifest = {
        'uuid': str(project.app_uuid),
        'shortName': project.app_short_name,
        'longName': project.app_long_name,
        'companyName': project.app_company_name,
        'versionLabel': project.app_version_label,
        'versionCode': 1,
        'watchapp': {
            'watchface': project.app_is_watchface
        },
        'appKeys': json.loads(project.app_keys),
        'resources': generate_resource_dict(project, resources),
        'capabilities': project.app_capabilities.split(','),
        'projectType': 'native',
        'sdkVersion': "2",
    }
    if project.app_is_shown_on_communication:
        manifest['watchapp']['onlyShownOnCommunication'] = project.app_is_shown_on_communication
    return manifest


def make_valid_package_manifest_name(short_name):
    """ Turn an app_short_name into a valid NPM package name. """
    name = short_name.lower()
    # Remove any invalid characters from the end
    name = re.sub(r'[^a-z0-9._]+$', '', name)
    # Any strings of invalid characters in the middle are converted to dashes
    name = re.sub(r'[^a-z0-9._]+', '-', name)
    # The name cannot start with [ ._] or end with spaces.
    name = name.lstrip(' ._').rstrip()
    return name


def generate_v3_manifest_dict(project, resources):
    manifest = {
        'name': make_valid_package_manifest_name(project.app_short_name),
        'author': project.app_company_name,
        'version': project.semver,
        'keywords': project.keywords,
        'dependencies': project.get_dependencies(),
        'pebble': {
            'displayName': project.app_long_name,
            'uuid': str(project.app_uuid),
            'sdkVersion': project.sdk_version,
            'watchapp': {
                'watchface': project.app_is_watchface
            },
            'messageKeys': json.loads(project.app_keys),
            'resources': generate_resource_dict(project, resources),
            'capabilities': project.app_capabilities.split(','),
            'projectType': project.project_type
        }
    }

    if project.project_type == 'package':
        manifest['files'] = ['dist.zip']
    else:
        manifest['pebble']['enableMultiJS'] = project.app_modern_multi_js
        if project.app_is_hidden:
            manifest['pebble']['watchapp']['hiddenApp'] = project.app_is_hidden
    if project.app_platforms:
        manifest['pebble']['targetPlatforms'] = project.app_platform_list
    return manifest


def generate_manifest_dict(project, resources):
    if project.is_native_or_package:
        if project.sdk_version == '2':
            return generate_v2_manifest_dict(project, resources)
        else:
            return generate_v3_manifest_dict(project, resources)
    elif project.project_type == 'simplyjs':
        return generate_simplyjs_manifest_dict(project)
    elif project.project_type == 'pebblejs':
        return generate_pebblejs_manifest_dict(project, resources)
    else:
        raise Exception(_("Unknown project type %s") % project.project_type)


def generate_resource_map(project, resources):
    return dict_to_pretty_json(generate_resource_dict(project, resources))


def dict_to_pretty_json(d):
    return json.dumps(d, indent=4, separators=(',', ': '), sort_keys=True) + "\n"


def generate_resource_dict(project, resources):
    if project.is_native_or_package:
        return generate_native_resource_dict(project, resources)
    elif project.project_type == 'simplyjs':
        return generate_simplyjs_resource_dict()
    elif project.project_type == 'pebblejs':
        return generate_pebblejs_resource_dict(resources)
    else:
        raise Exception(_("Unknown project type %s") % project.project_type)


def generate_native_resource_dict(project, resources):
    resource_map = {'media': []}
    for resource in resources:
        for resource_id in resource.get_identifiers():
            d = {
                'type': resource.kind,
                'file': resource.root_path,
                'name': resource_id.resource_id,
            }
            if resource_id.character_regex:
                d['characterRegex'] = resource_id.character_regex
            if resource_id.tracking:
                d['trackingAdjust'] = resource_id.tracking
            if resource_id.memory_format:
                d['memoryFormat'] = resource_id.memory_format
            if resource_id.storage_format:
                d['storageFormat'] = resource_id.storage_format
            if resource_id.space_optimisation:
                d['spaceOptimization'] = resource_id.space_optimisation
            if resource.is_menu_icon:
                d['menuIcon'] = True
            if resource_id.compatibility is not None:
                d['compatibility'] = resource_id.compatibility
            if project.sdk_version == '3' and resource_id.target_platforms:
                d['targetPlatforms'] = json.loads(resource_id.target_platforms)

            resource_map['media'].append(d)
    return resource_map


def generate_simplyjs_resource_dict():
    return {
        "media": [
            {
                "menuIcon": True,
                "type": "png",
                "name": "IMAGE_MENU_ICON",
                "file": "images/menu_icon.png"
            }, {
                "type": "png",
                "name": "IMAGE_LOGO_SPLASH",
                "file": "images/logo_splash.png"
            }, {
                "type": "font",
                "name": "MONO_FONT_14",
                "file": "fonts/UbuntuMono-Regular.ttf"
            }
        ]
    }


def generate_pebblejs_resource_dict(resources):
    media = [
        {
            "menuIcon": True,  # This must be the first entry; we adjust it later.
            "type": "bitmap",
            "name": "IMAGE_MENU_ICON",
            "file": "images/menu_icon.png"
        }, {
            "type": "bitmap",
            "name": "IMAGE_LOGO_SPLASH",
            "file": "images/logo_splash.png"
        }, {
            "type": "bitmap",
            "name": "IMAGE_TILE_SPLASH",
            "file": "images/tile_splash.png"
        }, {
            "type": "font",
            "name": "MONO_FONT_14",
            "file": "fonts/UbuntuMono-Regular.ttf"
        }
    ]

    for resource in resources:
        if resource.kind not in ('bitmap', 'png'):
            continue

        d = {
            'type': resource.kind,
            'file': resource.root_path,
            'name': re.sub(r'[^A-Z0-9_]', '_', resource.root_path.upper()),
        }
        if resource.is_menu_icon:
            d['menuIcon'] = True
            del media[0]['menuIcon']

        media.append(d)

    return {
        'media': media
    }


def generate_simplyjs_manifest(project):
    return dict_to_pretty_json(generate_simplyjs_manifest_dict(project))


def generate_simplyjs_manifest_dict(project):
    manifest = {
        "uuid": project.app_uuid,
        "shortName": project.app_short_name,
        "longName": project.app_long_name,
        "companyName": project.app_company_name,
        "versionLabel": project.app_version_label,
        "versionCode": 1,
        "capabilities": project.app_capabilities.split(','),
        "watchapp": {
            "watchface": project.app_is_watchface
        },
        "appKeys": {},
        "resources": generate_simplyjs_resource_dict(),
        "projectType": "simplyjs"
    }
    return manifest


def generate_pebblejs_manifest(project, resources):
    return dict_to_pretty_json(generate_pebblejs_manifest_dict(project, resources))


def generate_pebblejs_manifest_dict(project, resources):
    manifest = {
        "uuid": project.app_uuid,
        "shortName": project.app_short_name,
        "longName": project.app_long_name,
        "companyName": project.app_company_name,
        "versionLabel": project.app_version_label,
        "capabilities": project.app_capabilities.split(','),
        "versionCode": 1,
        "watchapp": {
            "watchface": project.app_is_watchface,
            'hiddenApp': project.app_is_hidden
        },
        "appKeys": {},
        "resources": generate_pebblejs_resource_dict(resources),
        "projectType": "pebblejs",
        "sdkVersion": "3",
    }
    if project.app_platforms:
        manifest["targetPlatforms"] = project.app_platform_list

    return manifest


def load_manifest_dict(manifest, manifest_kind, default_project_type='native'):
    """ Load data from a manifest dictionary
    :param manifest: a dictionary of settings
    :param manifest_kind: 'package.json' or 'appinfo.json'
    :return: a tuple of (models.Project options dictionary, the media map, the dependencies dictionary)
    """
    project = {}
    dependencies = {}
    if manifest_kind == APPINFO_MANIFEST:
        project['app_short_name'] = manifest['shortName']
        project['app_long_name'] = manifest['longName']
        project['app_company_name'] = manifest['companyName']
        project['app_version_label'] = manifest['versionLabel']
        project['app_keys'] = dict_to_pretty_json(manifest.get('appKeys', {}))
        project['sdk_version'] = manifest.get('sdkVersion', '2')
        project['app_modern_multi_js'] = manifest.get('enableMultiJS', False)

    elif manifest_kind == PACKAGE_MANIFEST:
        project['app_short_name'] = manifest['name']
        project['app_company_name'] = manifest['author']
        project['semver'] = manifest['version']
        project['app_long_name'] = manifest['pebble']['displayName']
        project['app_keys'] = dict_to_pretty_json(manifest['pebble'].get('messageKeys', []))
        project['keywords'] = manifest.get('keywords', [])
        dependencies = manifest.get('dependencies', {})
        manifest = manifest['pebble']
        project['app_modern_multi_js'] = manifest.get('enableMultiJS', True)
        project['sdk_version'] = manifest.get('sdkVersion', '3')
    else:
        raise InvalidProjectArchiveException(_('Invalid manifest kind: %s') % manifest_kind[-12:])

    project['app_uuid'] = manifest['uuid']
    project['app_is_watchface'] = manifest.get('watchapp', {}).get('watchface', False)
    project['app_is_hidden'] = manifest.get('watchapp', {}).get('hiddenApp', False)
    project['app_is_shown_on_communication'] = manifest.get('watchapp', {}).get('onlyShownOnCommunication', False)
    project['app_capabilities'] = ','.join(manifest.get('capabilities', []))

    if 'targetPlatforms' in manifest:
        project['app_platforms'] = ','.join(manifest['targetPlatforms'])
    if 'resources' in manifest and 'media' in manifest['resources']:
        media_map = manifest['resources']['media']
    else:
        media_map = {}
    project['project_type'] = manifest.get('projectType', default_project_type)
    return project, media_map, dependencies
