from os import environ, unlink, makedirs, symlink
from os.path import dirname, exists, isdir
import re
import tempfile

"""
This class is supposed to make symlinks from your home directory (ex. /afs) to
a faster directory ( local /tmp). 
"""
regex = re.compile('^(.*)\$\((.+?)\)(.*)$')


class ProdSymLinks():

    def __init__(self):
        self.symlinks = {}
        self.readlinks()

    def readlinks(self):
        """
        Will read 'symlink' file from home directory, parse it and expand it.
        Will store results in self.symlink for later use.
        """
        file = environ["HOME"] + "/.scramrc/symlinks"
        with open(file) as f_in:
            for line in f_in.readlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                link, path, _ = line.split(":", 2)
                link = dirname(link)
                m = regex.match(link)
                while m:
                    link = m.group(1) + environ[m.group(2)] + m.group(3)
                    m = regex.match(link)
                self.symlinks[link] = path
                print(link)
        return

    def mklink(self, store):
        link = store
        link = dirname(link)
        path_to_check = "{0}/{1}".format(environ("LOCALTOP"), link)
        if not exists(path_to_check):
            unlink(path_to_check)
            if link in self.symlinks:
                path = self.symlinks[link]
                m = regex.match(path)
                while m:
                    path = m.group(1) + environ[m.group(2)] + m.group(3)
                    m = regex.match(path)
                makedirs(path, 0o755)
                path = tempfile.mkdtemp(prefix=link + '.', dir=path)
                if path and isdir(path):
                    sym_link = "{0}/{1}".format(environ("LOCALTOP"), link)
                    symlink(path, sym_link)
        return