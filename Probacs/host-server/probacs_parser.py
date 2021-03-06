"""
parser.py: parser utility for user uploaded task file, 
            user uploaded profile file and user uploaded
            compiler configuration file
Author: Shipei Zhou
Email: shipeiz@andrew.cmu.edu
Date: May 27, 2018
"""
import sys
import copy

def parseTaskFile(filename):
    """
    args:
    filename: name of the user uploaded task file
    return:
    tuple, tuple[0] = parse message, None for no problem, string for any error
    tuple[1] = list of dicts of parsed content
    """
    line_no = 0
    d = {}
    with open(filename) as file:
        while True:
            line_no += 1
            line = file.readline()
            # print(line)
            if not line or line.strip() == "":
                break

            if ':' not in str(line):
                msg = "Malformatted line %d: no ':'' found"%line_no
                return msg, None
            
            tokens = filter(lambda x: x, line.split(":", 1))
            tokens = map(lambda x: x.strip(), tokens)
            
            tokens = list(tokens)
            # print(len(tokens)==2)
            if len(tokens) != 2:
                msg = "Malformatted line %d: must be in key:value format"%line_no
                return msg, None
            
            key = tokens[0]
            value = tokens[1]
            
            if key in d:
                msg = "Duplicate key at line %d: %s already speficied"%(line_no, key)
                return msg, None
            
            if key in ["profile", "target_os", "compiler", "version", 'command']:
                value = value.split(",")
                value = filter(lambda x: x, map(lambda x: x.strip(), value))
                value = list(value)
                # print(list(value))
            d[key] = value

    for key in ['target_os', 'compiler', 'version', 'profile', 'username']:
        if key not in d:
            msg = "Must specify %s in the task file"%(key)
            return msg, None

    if not d['username']:
        msg = "Must specify non-null username"
        return msg, None

    if len(d['target_os']) != len(d['compiler']) or len(d['target_os']) != len(d['version']):
        msg = "Number of target_os, compiler and version must be the same"
        return msg, None

    if 'command' in d and len(d['target_os']) != len(d['command']):
        msg = "Number of command, target_os, compiler and version must be the same"
        return msg, None

    ret = []

    task = {'profile': d['profile'], 'username': d['username']}
    
    task['tag'] = d.get('tag', '')

    for i in range(len(d['target_os'])):
        task['target_os'] = d['target_os'][i]
        task['compiler'] = d['compiler'][i]
        task['version'] = d['version'][i]
        if 'command' in d:
            task['command'] = d['command'][i]
        ret.append(copy.deepcopy(task))

    return None, ret

def parseCompilerFile(filename):
    line_no = 0
    d = {}
    with open(filename) as file:
        while True:
            line_no += 1
            line = file.readline()
            if not line or line.strip() == "":
                break

            if ':' not in str(line):
                msg = "Malformatted line %d: no ':' found"%line_no
                return msg, None

            tokens = filter(lambda x: x, line.split(":"))
            tokens = map(lambda x: x.strip(), tokens)
            
            tokens = list(tokens)
            # print(len(tokens)==2)
            if len(tokens) != 2:
                msg = "Malformatted line %d: must be in key:value format"%line_no
                return msg, None
            
            key = tokens[0]
            value = tokens[1]

            if key in d:
                msg = "Duplicate key at line %d: %s already speficied"%(line_no, key)
                return msg, None

            if key not in ['target_os', 'compiler', 'version', 'ip', 'port', 'invoke_format', 'flag']:
                msg = "Illegal key %s at line %d"%(key, line_no)

            if key == 'flag':
                value = list(map(lambda x: x.strip(), value.split(',')))

            d[key] = value

    for key in ['target_os', 'compiler', 'version', 'ip', 'port', 'invoke_format', 'flag']:
        if key not in d:
            msg = "Missing key %s in configuration file"%key
            return msg, None

    # if not d['ip'].starts('http://'):
    d['ip'] = 'http://' + d['ip']

    return None, d

def parseProfileFile(filename):
    line_no = 0
    d = {}
    with open(filename) as file:
        while True:
            line_no += 1
            line = file.readline()
            # print(line)
            if not line or line.strip() == "":
                break

            if 'flag' in d:
                d['flag'].append(line.strip())
                continue

            if ':' not in str(line):
                msg = "Malformatted line %d: no ':'' found"%line_no
                return msg, None
            
            tokens = map(lambda x: x.strip(), line.split(":"))
            tokens = filter(lambda x: x != None and x != "", tokens)
            
            tokens = list(tokens)
            if len(tokens) == 1 and tokens[0] == 'flag':
                d['flag'] = []
                continue

            # print(len(tokens)==2)
            if len(tokens) != 2:
                msg = "Malformatted line %d: must be in key:value format"%line_no
                return msg, None
            
            key = tokens[0]
            value = tokens[1]
            
            if key in d:
                msg = "Duplicate key at line %d: %s already speficied"%(line_no, key)
                return msg, None
            d[key] = value

    for key in ['target_os', 'compiler', 'version', 'uploader', 'name', 'flag']:
        if key not in d:
            msg = "Must specify %s in the profile configuraton file"%key
            return msg, None

    return None, d



if __name__ == "__main__":
    print(parseTaskFile(sys.argv[1]))