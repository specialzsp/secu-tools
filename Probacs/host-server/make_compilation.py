#!/usr/bin/env python
import os, sys
from subprocess import Popen, PIPE

def do_compilation(src_file, dest_folder, invoke_format, flags):
    """
    example invoke_format: gcc_flags_source_-o_exename
    """
    invoke_format = invoke_format.replace("_", " ")
    flags = flags.replace("_", " ")
    flags = flags.split(",")

    if os.name == 'nt':
        delimit = "\\"
    else:
        delimit = "/"

    name, extension = src_file.split(delimit)[-1].split('.')

    if dest_folder[-1] == delimit:
        dest_folder = dest_folder[0:-1]



    if os.path.exists(dest_folder) and not os.path.isdir(dest_folder):
        sys.stderr.write("Output directory already exists!\n")
        sys.stderr.flush()
        exit(-1)

    if not os.path.exists(dest_folder):
        os.mkdir(dest_folder)

    dest_folder += delimit
    log_filename = dest_folder + name + ".log"
    log_file = open(log_filename, "w")

    print("compilation begins...")
        
    cnt = 0
    for flag in flags:
        cnt += 1
        exename = dest_folder + name + "_%d_%s"%(cnt, flag.replace(" ", "_"))
        logline = "%s\t%s"%(exename, flag)

        command = invoke_format.replace("flags", flag).replace("source", src_file).replace("exename", exename).split(" ")
        print(command)
        compilation = Popen(command, stdout=PIPE, stderr=PIPE)
        out, err = compilation.communicate()
        log_file.write("%s, %s, %s\n"%(logline, out, err))

    log_file.close()
    print("compilation done!")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.stderr.write("Usage: python make_compilation <source file> <output dir> <invoke_format> <flags>\n")
        sys.stderr.flush()
        exit(-1)
    cur_id = os.getpid()
    print(cur_id)
    do_compilation(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
