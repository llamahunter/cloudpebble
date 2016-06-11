import zipfile
import os


def zip_directory(input_dir, output_zip, preserve_empty=False):
    """ Zip up a directory and preserve symlinks
    Adapted from https://gist.github.com/kgn/610907
    :param input_dir: Directory to zip up
    :param output_zip: Location of output file
    :param preserve_empty: Whether to allow empty directories
    :return:
    """
    zip_out = zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED)

    root_len = len(os.path.dirname(input_dir))

    def archive_directory(parent_directory):
        contents = os.listdir(parent_directory)
        # Do not allow empty directories
        if not contents:
            if preserve_empty:
                # http://www.velocityreviews.com/forums/t318840-add-empty-directory-using-zipfile.html
                archive_root = parent_directory[root_len:].replace('\\', '/').lstrip('/')
                zip_info = zipfile.ZipInfo(archive_root+'/')
                zip_out.writestr(zip_info, '')
            else:
                raise ValueError("Input directory should not contain any empty directories.")
        for item in contents:
            full_path = os.path.join(parent_directory, item)
            if os.path.isdir(full_path) and not os.path.islink(full_path):
                archive_directory(full_path)
            else:
                archive_root = full_path[root_len:].replace('\\', '/').lstrip('/')
                if os.path.islink(full_path):
                    # http://www.mail-archive.com/python-list@python.org/msg34223.html
                    zip_info = zipfile.ZipInfo(archive_root)
                    zip_info.create_system = 3
                    # Long type of hex val of '0xA1ED0000L',
                    # say, symlink attr magic...
                    zip_info.external_attr = 2716663808L
                    zip_out.writestr(zip_info, os.readlink(full_path))
                else:
                    zip_out.write(full_path, archive_root, zipfile.ZIP_DEFLATED)

    archive_directory(input_dir)

    zip_out.close()
