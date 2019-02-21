from SCRAM.BuildSystem.SimpleDoc import SimpleDoc
from re import compile
from os import environ
from os.path import exists
from json import dump
from SCRAM import printmsg

reReplaceEnv = [compile('^(.*)(\$\((\w+)\))(.*)$'),
                compile('^(.*)(\$\{(\w+)\})(.*)$'),
                compile('^(.*)(\$(\w+))(.*)$')]


class ToolFile(object):
    def __init__(self):
        self.parser = SimpleDoc()
        self.parser.add_callback('tool', self._tool_callback)
        return

    def save_json(self, outfile):
        with open(outfile, 'w') as ref:
            dump(self.contents, ref, sort_keys=True, indent=2)
        return

    def parse(self, filename):
        self._clean(filename)
        data = self.parser.parse(filename)
        self._update_env(data)
        for k in self.env:
            self.env[k] = self._fix_data(self.env[k])
        if not self._update_contents(data):
            if self.warnings:
                printmsg('%s' % '\n'.join(self.warnings))
            return False
        for key in list(self.contents):
            if not self.contents[key]:
                del self.contents[key]
        return True

    def _clean(self, filename=None):
        self.filename = filename
        self.warnings = []
        self.contents = {'USE': [], 'LIB': [], 'INCLUDE': [], 'LIBDIR': [],
                         'BINDIR': [], 'TOOLNAME': '', 'TOOLVERSION': '',
                         'VARIABLES': [], 'LIBTYPES': [], 'RUNTIME': {}, 'FLAGS': {}}
        self.env = {}

    def _update_env(self, data):
        if data.tag == 'environment':
            key = 'default'
            if 'value' in data.attrib:
                key = 'value'
            var = data.attrib['name']
            self.env[var] = data.attrib[key]
            if var not in self.contents['VARIABLES']:
                self.contents['VARIABLES'].append(var)
        for child in list(data):
            self._update_env(child)

    def _fix_data(self, data):
        while '$' in data:
            for regex in reReplaceEnv:
                m = regex.match(data)
                if m:
                    key = m.group(3)
                    value = ''
                    if key in self.env:
                        value = self.env[key]
                    elif key in environ:
                        value = environ[key]
                    else:
                        print('ERROR: Unable to replace %s in %s' % (m.group(2), self.filename))
                    data = '%s%s%s' % (m.group(1), value, m.group(4))
                    break
        return data

    def _tool_callback(self, root, start_event, args):
        if start_event:
            self.parser.add_filter("ifversion", root.attrib['version'])

    def _check_path(self, path, handler):
        msg = 'OK'
        if not exists(path):
            if handler == 'WARN':
                msg = 'OK (but currently missing)'
            else:
                msg = 'FAIL'
            self.warnings.append('Checks [%s] for %s' % (msg, path))
        return msg != 'FAIL'

    def _update_contents(self, data):
        tag = data.tag.upper()
        if tag == 'TOOL':
            self.contents['TOOLNAME'] = data.attrib['name'].lower()
            self.contents['TOOLVERSION'] = data.attrib['version']
            if 'type' in data.attrib:
                vtype = data.attrib['type'].upper()
                if vtype == 'SCRAM':
                    self.contents['SCRAM_PROJECT'] = 1
                elif vtype == 'COMPILER':
                    self.contents['SCRAM_COMPILER'] = 1
                else:
                    print ('ERROR: Unknow tool type %s found in %s' %
                           (data.attrib['type'], self.filename))
        elif tag == 'USE':
            self.contents['USE'].append(data.attrib['name'].lower())
        elif tag == 'LIB':
            self.contents['LIB'].append(data.attrib['name'])
        elif tag == 'ENVIRONMENT':
            value = data.attrib['default'] if 'default' in data.attrib else data.attrib['value']
            value = self._fix_data(value)
            tag = data.attrib['name'].upper()
            if tag == '%s_BASE' % self.contents['TOOLNAME'].upper().replace('-', '_'):
                self.contents[tag] = value
            elif tag in self.contents:
                if isinstance(self.contents[tag], str):
                    self.contents[tag] = [self.contents[tag]]
                if value not in self.contents[tag]:
                    self.contents[tag].append(value)
            else:
                self.contents[tag] = value
        elif tag == 'FLAGS':
            flag_name = list(data.attrib)[0]
            tag = flag_name.upper()
            value = self._fix_data(data.attrib[flag_name])
            if tag not in self.contents['FLAGS']:
                self.contents['FLAGS'][tag] = []
            for flag in [f for f in value.split(' ') if f]:
                if flag not in self.contents['FLAGS'][tag]:
                    self.contents['FLAGS'][tag].append(flag)
        elif tag == 'RUNTIME':
            tag = data.attrib['name']
            value = data.attrib['default'] if 'default' in data.attrib else data.attrib['value']
            vtype = ''
            if 'type' in data.attrib:
                vtype = data.attrib['type'].upper()
            handler = ''
            if 'handler' in data.attrib:
                handler = data.attrib['handler'].upper()
            value = self._fix_data(value)
            if vtype == 'PATH':
                if not self._check_path(value, handler):
                    return False
                tag = 'PATH:%s' % tag
            else:
                tag = '%s' % tag
            if tag not in self.contents['RUNTIME']:
                self.contents['RUNTIME'][tag] = []
            if value not in self.contents['RUNTIME'][tag]:
                self.contents['RUNTIME'][tag].append(value)
        elif tag in ['CLIENT', 'ROOT', 'INFO'] or self.parser.has_filter(data.tag):
            pass
        else:
            print('ERROR: Unknown tag %s found in %s.' % (data.tag, self.filename))
        for child in list(data):
            if not self._update_contents(child):
                return False
        return True

    def summarize_tool(tool):
        data = {}
        if 'SCRAM_PROJECT' in tool:
            data['SCRAM_PROJECT'] = 'yes'
        if 'SCRAM_COMPILER' in tool:
            data['SCRAM_COMPILER'] = 'yes'
        if 'VARIABLES' in tool:
            for var in tool['VARIABLES']:
                if isinstance(tool[var], str):
                    data[var] = tool[var]
                else:
                    data[var] = ' '.join(tool[var])
        if 'MAKEFILE' in tool:
            data[''] = ' '.join(tool['MAKEFILE'])
        if 'FLAGS' in tool:
            for flag in tool['FLAGS']:
                data[flag] = ' '.join(tool['FLAGS'][flag])
        for extra in ['LIB', 'LIBDIR', 'INCLUDE', 'USE']:
            if extra not in tool:
                continue
            data[extra] = ' '.join(tool[extra])
        if 'RUNTIME' in tool:
            for var in tool['RUNTIME']:
                vname = var
                if ':' in var:
                    vtype, vname = var.split(':', 1)
                data[vname] = ':'.join(tool['RUNTIME'][var])
        return data

    def get_feature(tool, tag=None):
        value = ''
        if tag:
            ref = tool
            for s in tag.split('.'):
                if s in ref:
                    ref = ref[s]
                else:
                    SCRAM.scramerror('SCRAM: No type of variable called "%s" defined for this tool.' % tag)
            if isinstance(ref, list):
                value = ' '.join(ref)
            else:
                value = ref
        else:
            for tag in sorted([t for t in tool if t not in ['VARIABLES']]):
                if isinstance(tool[tag], dict):
                    for v in sorted(tool[tag]):
                        value += "%s.%s\n" % (tag, v)
                else:
                    value += '%s\n' % tag
        return value
