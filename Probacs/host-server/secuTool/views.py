import os, tempfile, zipfile, tarfile, time, json,signal
from subprocess import Popen, PIPE
from django.utils import timezone
from datetime import datetime
from wsgiref.util import FileWrapper
from django.shortcuts import render, redirect
from secuTool.forms import *
from secuTool.models import *
from django.core.files import File
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import requests
from django.conf import settings
from probacs_parser import *
from django.core import serializers
from io import BytesIO
import zipfile,io,base64
from django.db.models import Q
from helper import *
# Create your views here.
################################
# global variables
# winurl = 'http://172.16.165.132:8000'
host_ip_gateway = settings.GATEWAY
enable_test = settings.ENABLE_LOCALTEST
print(enable_test)
self_ip = settings.LOCAL_IP
print(self_ip)
# winurl = 'http://192.168.56.102:8000' #winurl for virtualbox
testurl = 'http://httpbin.org/post'  #test request headers
rootDir = 'Compilation_tasks/'
tempDir = 'temp/'
# the datastructure  is stored in settings
################################


#**************#**************#**************#**************
#**************    develop log#**************#**************
'''
    1. command for popen when compiling is not valid
        - wrap try//err ?
    5. requests error checking
    6. concurrent search-based download?

'''
#**************#**************#**************#**************

##############################################################################################
##############################################################################################
##################. function for main page ################################################
##############################################################################################
def home(request):
    context = {}
    context['form'] = ProfileUserForm()
    context['nav1'] = "active show"
    profiles = Profile_conf.objects.values()
    profile_dict = {}
    for profile in profiles:
        target_os, compiler, name = profile["target_os"], profile["compiler"] + " " + profile["version"], profile["name"]
        if target_os not in profile_dict:
            profile_dict[target_os] = {}
        if compiler not in profile_dict[target_os]:
            profile_dict[target_os][compiler] = []
        profile_dict[target_os][compiler].append(name)

    context['json_profiles'] = json.dumps(profile_dict)
    # context['status'] = statuses
    return render(request, 'secuTool/test.html',context)

@csrf_exempt
def peek_profile(request):
    target_os = request.POST['target_os']
    compiler, version = request.POST['compiler'].split(' ')
    name = request.POST['name']

    profile = Profile_conf.objects.filter(name=name,
                                        target_os=target_os,
                                        compiler=compiler,
                                        version=version)

    num = profile.count()
    if num > 1:
        res = {"message":"Multiple profiles found with given information"}
    elif num < 1:
        res = {"message":"No profile matching given information"}
    else:
        res = {"target_os": profile[0].target_os,
                "compiler": profile[0].compiler,
                "version": profile[0].version,
                "name": profile[0].name,
                "uploader": profile[0].uploader,
                "upload_time": profile[0].upload_time,
                "flag": profile[0].flag}

    return HttpResponse(json.dumps(res), content_type="application/json")


##############################################################################################
##############################################################################################
##################. function for preview page ################################################
##############################################################################################

@transaction.atomic
def preview(request):
    context = {}
    #######################################
    ## register task metadata, tasks, generate preview parameters
    #######################################
    message, res = register_tasks(request)
    if message:
        return render(request, 'secuTool/test.html', {"message":message})
    # print(res)
    context = {}
    context['rows'] = res["rows"]
    context['taskid'] = res["taskName"]
    context['json_flags'] = json.dumps(res["flag_list"])
    return render(request, 'secuTool/preview.html',context)

@transaction.atomic
@csrf_exempt
def cmdline_preview(request):
    '''
    cmdline view function for generating preview parameters
    '''
    message, res = register_tasks(request)
    response = {}
    if message:
        response['message'] = message
        return HttpResponse(json.dumps(response),content_type="application/json")
    response['rows'] = res["rows"]
    response['taskid'] = res["taskName"]
    return HttpResponse(json.dumps(response),content_type="application/json")

##############################################################################################
##############################################################################################
##################. function for compilation redirect ########################################
##############################################################################################

@csrf_exempt
@transaction.atomic
def param_upload(request):
    '''
    get updated compilation parameters from user, write db with new subtasks, deliver compilation tasks to
    platforms in asyn calls
    '''
    task_name = request.POST['taskid']
    task_num = request.POST['taskCount']
    task_params = []
    #####################
    ##retrieve source file path/ name, config source path, output path, etc,
    #####################
    cur_taskMeta = TaskMeta.objects.get(task_id=task_name)
    filename = cur_taskMeta.src_filename
    taskFolder = rootDir+task_name
    codeFolder = taskFolder+"/"+"src"
    srcPath = filename
    #####################
    ## parse params from requests
    #####################
    # ensure all compilation on single machine with same compiler will be packed together
    single_vm_ref = {}
    vm_num = 0
    for i in range(int(task_num)):
        obj = {}
        task_id = 'tasks['+str(i)+']'
        os = task_id+'[os]'
        compiler = task_id+'[compiler]'
        profile = task_id+'[profile]'
        flag = task_id+'[flag]'
        username = task_id+'[username]'
        tag = task_id+'[tags]'
        command = task_id+'[command]'
        ref_key = request.POST[os].strip()+"|"+request.POST[compiler].strip()
        # print(ref_key)
        if ref_key in single_vm_ref.keys():
            ## task already exists, pack extra flags
            obj = task_params[single_vm_ref[ref_key]]
            new_flags = request.POST[flag].split(",")
            new_flags = "_".join([ele.strip() for ele in new_flags])
            obj['flag'] = obj['flag']+","+new_flags
        else:
            ## no task with same destination, establish a new one
            obj['target_os'] = request.POST[os]
            compiler_full = request.POST[compiler].split(" ")
            obj['compiler'] = compiler_full[0]
            obj['version'] = compiler_full[1]
            obj['profile'] = request.POST[profile]
            obj['flag'] = request.POST[flag].split(",")
            obj['flag'] = "_".join([ele.strip() for ele in obj['flag']])
            obj['username'] = request.POST[username]
            obj['tags'] = request.POST[tag]
            obj['command'] = request.POST[command]
            single_vm_ref[ref_key] = vm_num
            vm_num += 1
            task_params.append(obj)
    #####################
    #form request format from obj for each task
    #####################
    # print(task_params)
    response = {}
    task_num, server_alive = call_compile(task_params,enable_test,filename, taskFolder, codeFolder, srcPath, task_name,self_ip,host_ip_gateway)
    print(server_alive)
    if not server_alive:
        response['message'] = "platform server is not responding !"
        return HttpResponse(json.dumps(response),content_type="application/json")
    cur_taskMeta.compilation_num = task_num
    cur_taskMeta.save()
    
    response['taskid'] = task_name
    return HttpResponse(json.dumps(response),content_type="application/json")


@csrf_exempt
def cmdline_compile(request):
    '''
    form task_params
    '''
    jsonDec = json.decoder.JSONDecoder()
    req = jsonDec.decode(request.POST['content'])
    response = {}
    ## form general parameters
    task_name = req['taskid']
    ##form task_param object
    task_p = req['rows']
    # print(task_p)
    task_params = []
    compilerDict = {}
    for ele in task_p:
        if ele['compiler'] in compilerDict.keys():
            ## already has same target compilation
            obj = task_params[compilerDict[ele['compiler']]]
            flaglist = ele['flag'].split(",")
            new_flag = "_".join([i.strip() for i in flaglist])
            obj['flag'] +=","+new_flag
        else:
            obj = {}
            obj['target_os'] = ele['target_os']
            compiler_full = ele['compiler'].split(" ")
            obj['compiler'] = compiler_full[0]
            obj['version'] = compiler_full[1]
            compilerDict[ele['compiler']] = len(task_params)
            obj['tags'] = ele['tag']
            obj['username'] = ele['username']
            obj['profiles'] = ele['profiles']
            flaglist = ele['flag'].split(",")
            obj['flag'] = "_".join([i.strip() for i in flaglist])
            obj['command'] = ele['command']
            task_params.append(obj)
    print(task_params)

    cur_taskMeta = TaskMeta.objects.get(task_id=task_name)
    filename = cur_taskMeta.src_filename
    taskFolder = rootDir+task_name
    codeFolder = taskFolder+"/"+"src"
    srcPath = filename
    # print(params)
    task_num, isalive = call_compile(task_params,enable_test,filename, taskFolder, codeFolder, srcPath, task_name, self_ip, host_ip_gateway)
    
    if not isalive:
        response['status'] = "false"
        response['message'] = "platform server is not responding !"
        return HttpResponse(json.dumps(response),content_type="application/json")
    cur_taskMeta.compilation_num = task_num
    cur_taskMeta.save()
    response['status'] = "true"
    response['message'] = "The task id is " +task_name
    response['taskid'] = task_name
    return HttpResponse(json.dumps(response),content_type="application/json")


##############################################################################################
##############################################################################################
##################. function for saving compilation results && download request ##############
##############################################################################################

@csrf_exempt
def saveExe(request):
    taskFolder = request.POST['taskid']
    filename = request.FILES['file'].name
    basedir = rootDir+taskFolder+'/'
    #create 'secu_compile' folder to be default folder containing all the tasks
    if not os.path.exists(basedir+'secu_compile'):
        os.system('mkdir '+basedir+'secu_compile')
    # print(filename)
    basedir += 'secu_compile/'
    with open(basedir+filename,'wb+') as dest:
        for chunk in request.FILES['file'].chunks():
            dest.write(chunk)
    #untar archive, delete archive
    os.system('tar xvzf '+ basedir+filename+" -C "+basedir)
    os.system('rm '+basedir+filename)
    response = HttpResponse()
    response.write("file received")

    return response

def wrap_dir(request):
    '''
    download files based on whole task level
    '''
    taskFolder = request.POST['downloadtaskid']
    if taskFolder == None or taskFolder == "" or TaskMeta.objects.filter(task_id=taskFolder).count() == 0:
        message = "there is no corresponding tasks"
        return render(request, 'secuTool/test.html', {"message":message, "nav4":"active show"})
    print("taskFolder: "+taskFolder )

    #pack executables inside task folder, send back
    new_name = "archive_"+taskFolder+".tgz"
    current_rootDir = rootDir+taskFolder+'/'
    with tarfile.open(current_rootDir+new_name, "w:gz") as tar:
        tar.add(current_rootDir+'secu_compile', arcname=os.path.basename(current_rootDir+'secu_compile'))

    compressed_dir = open(current_rootDir+new_name,'rb')
    response = HttpResponse(compressed_dir,content_type='application/tgz')
    response['Content-Disposition'] = 'attachment; filename='+new_name
    # os.system("rm "+taskFolder+'/'+new_name)
    return response

@csrf_exempt
def cmdline_download(request):
    taskFolder = request.POST['task_id']
    print("taskFolder: "+taskFolder )
    new_name = "archive_"+taskFolder+".tgz"
    current_rootDir = rootDir+taskFolder+'/'
    with tarfile.open(current_rootDir+new_name, "w:gz") as tar:
        tar.add(current_rootDir+'secu_compile', arcname=os.path.basename(current_rootDir+'secu_compile'))

    compressed_dir = open(current_rootDir+new_name,'rb')
    response = HttpResponse(compressed_dir,content_type='application/tgz')
    response['Content-Disposition'] = 'attachment; filename='+new_name
    # os.system("rm "+taskFolder+'/'+new_name)
    return response


@csrf_exempt
def download_search(request):
    ## remains earcgh params when privide dowload
    obj = dict(request.POST)
    print(obj['exe_pair'])
    # token = datetime.now.strftime()
    new_name = "archive_searchReqest.tgz"
    with tarfile.open(new_name, "w:gz") as tar:
        for ele in obj['exe_pair']:
            taskFolder,platformFolder,exename = ele.split("$%$")
            exe_path = rootDir+taskFolder+"/secu_compile/"+platformFolder+"/"
            for f in os.listdir(exe_path):
                if str(f).startswith(exename):
                    tar.add(exe_path+f, arcname=os.path.join(taskFolder,f))
    compressed_dir = open(new_name,'rb')
    response = HttpResponse(compressed_dir,content_type='application/tgz')
    response['Content-Disposition'] = 'attachment; filename='+new_name
    return response


##############################################################################################
##############################################################################################
##################. function for search page #################################################
##############################################################################################


def search_panel(request):
    context = {}
    context['nav3'] = "active show"
    return render(request, 'secuTool/test.html',context)

@transaction.atomic
def check_status(request):
    '''
    called when search request encountered
    '''
    total_count = 7
    empty_count, query_dict, flags, compilers, context = construct_querySet(request)
    context['nav3'] = "active show"

    if empty_count == total_count:
        context['search_result'] = "-- Showing 0 result of user request."
        return render(request, 'secuTool/test.html',context)

    print(query_dict)
    context, obj = form_search_response(query_dict,flags,compilers,context)

    context['search_result'] = "-- Showing "+str(obj.count())+" results of user request."
    if request.POST['if_all'] == 'true': #if showing all jobs, delete search message
        context['compilers'] = ''
    return render(request, 'secuTool/test.html',context)

@transaction.atomic
@csrf_exempt
def cmdline_search(request):
    total_count = 7
    response = {}
    empty_count, query_dict, flags, compilers, context = construct_querySet(request)
    if empty_count == total_count:
        response['message'] = "Your search has no matched results."
        return HttpResponse(json.dumps(response),content_type="application/json")

    context, obj = form_search_response(query_dict,flags,compilers,context)
    response = serializers.serialize('json',context['tasks'])
    # response['message'] = "-- Showing "+str(obj.count())+" results of user request."
    return HttpResponse(response,content_type="application/json")
##############################################################################################
##############################################################################################
##################. function for ajax tracking/ update########################################
##############################################################################################
@csrf_exempt
def terminate(request):
    task_id = request.POST['task_id']
    subtasks = Task.objects.filter(task_id=task_id)

    response = {}
    response['task_id'] =task_id
    ## rewrite subtask status
    hasOngoing = False
    for ele in subtasks:
        if ele.status == "ongoing":
            ele.status = "terminated"
            hasOngoing = True
        ele.save()
    ## terminate tasks based on platform if has ongoing tasks
    if hasOngoing:
        taskMeta = TaskMeta.objects.get(task_id=task_id)
        terminate_process(task_id, taskMeta, enable_test)
    finished, log_report = form_log_report(subtasks)
    response['total'] = subtasks.count()
    response['finished'] = finished
    response['log_report'] = log_report
        
    return HttpResponse(json.dumps(response),content_type="application/json") 

@csrf_exempt
def cmdline_terminate(request):
    response = {}
    task_id = request.POST['task_id']
    subtasks = Task.objects.filter(task_id=task_id)
    # response['task_id'] = task_id
    if subtasks.count() == 0:
        response['message'] = "task: "+task_id+" does not exist!"
        return HttpResponse(json.dumps(response),content_type="application/json")
    hasOngoing = False
    for ele in subtasks:
        if ele.status == "ongoing":
            ele.status = "terminated"
            hasOngoing = True
        ele.save()
    if hasOngoing:
        taskMeta = TaskMeta.objects.get(task_id=task_id)
        status = terminate_process(task_id, taskMeta,enable_test)
        response['message'] = "task: "+task_id+" has been successfully terminated !" 
    else:
        response['message'] = "task: "+task_id+" is already finished" 
    # finished, log_report = form_log_report(subtasks)

    
    # response['log_report'] = log_report
    return HttpResponse(json.dumps(response),content_type="application/json")

# @transaction.atomic
@csrf_exempt
def rcv_platform_result(request):
    '''
    called when platform server sending back compilation result for each single compilation
    '''
    task = Task.objects.get(task_id=request.POST['task_id'],flag=request.POST['flag'].replace(" ","_"),
        target_os=request.POST['target_os'],compiler=request.POST['compiler'],version=request.POST['version'])
    task.out = request.POST['out']
    task.err = request.POST['err']
    task.platform_folder = request.POST['platform_folder']
    task.finish_tmstmp=datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    task.status = request.POST['status']
    print('update from platform '+ str(request.POST['platform_folder']) +'finished')
    task.save()
    return HttpResponse()


def redirect_trace(request):
    '''
    refresh ajax page, return first several tasks
    invoked whenever the tab has been clicked
    '''
    context = {}
    task_number = 5
    current_id = None
    if 'ongoing' in request.GET:
        current_id = request.GET['ongoing']
        context['ongoing_display'] = 'block'
    else:
        context['ongoing_display'] = 'none'
    ## now retrieve top five in database
    ## form a dictionary adn return
    tasks_report = []
    if current_id == None: #simply retrieve 5
        obj = TaskMeta.objects.all().order_by('-id')[:task_number]
        print(obj.count())
        for ele in obj:
            tasks_report.append(parse_taskMeta(ele, False))
    else:
        tasks_report.append(parse_taskMeta(TaskMeta.objects.get(task_id=current_id),True))
        obj = TaskMeta.objects.all().order_by('-id')
        task_number -= 1
        for ele in TaskMeta.objects.all().order_by('-id'):
            if ele.task_id == current_id:
                continue
            else:
                task_number -= 1
                tasks_report.append(parse_taskMeta(ele,False))
                if task_number == 0:
                    break
    print(tasks_report)
    context['nav4'] = "active show"
    context['tracing_tasks'] = tasks_report
    context['ongoing_tasks'] = current_id
    # context['status'] = statuses
    return render(request, 'secuTool/test.html',context)


def trace_task_by_id(request):
    '''
    trace task used for new ui, return
    '''
    task_id = request.GET['task_id']
    obj = Task.objects.filter(task_id=task_id)
    response = {}
    response['total'] = obj.count()
    finished, log_report = form_log_report(obj)
    response['finished'] = finished
    response['task_id'] = task_id
    response['log_report'] = log_report
    return HttpResponse(json.dumps(response),content_type="application/json")

##############################################################################################
##############################################################################################
##################. function for profile/compiler configuration management ##################
##############################################################################################

@csrf_exempt
def addCompiler(request):
    if 'compiler_file' not in request.FILES:
        context = {'nav2':'active show', 'message':'No compiler file uploaded'}
        return render(request, "secuTool/test.html", context)

    compiler_conf_path = tempDir + request.FILES['compiler_file'].name
    with open(compiler_conf_path, 'wb+') as dest:
        for chunk in request.FILES['compiler_file'].chunks():
            dest.write(chunk)

    message, compiler = parseCompilerFile(compiler_conf_path)
    if message:
        return render(request, 'secuTool/test.html', {"message":message, "nav2":"active show"})


    new_compiler = Compiler_conf(target_os=compiler['target_os'],
                                    compiler=compiler['compiler'],
                                    version=compiler['version'],
                                    ip=compiler['ip'],
                                    port=compiler['port'],
                                    invoke_format=compiler['invoke_format'],
                                    flag=json.dumps(compiler['flag']))
    new_compiler.save()

    context = {"message":"New compiler added successfully",
                "nav2":"active show"}
    return render(request, "secuTool/test.html", context)

@csrf_exempt
def addProfile(request):
    if 'profile_file' not in request.FILES:
        context = {'nav2':'active show', 'message':'No profile file uploaded'}
        return render(request, "secuTool/test.html", context)

    profile_conf_path = tempDir + request.FILES['profile_file'].name
    with open(profile_conf_path, 'wb+') as dest:
        for chunk in request.FILES['profile_file'].chunks():
            dest.write(chunk)

    message, profile = parseProfileFile(profile_conf_path)
    if message:
        return render(request, 'secuTool/test.html', {"message":message, "nav2":"active show"})

    old_profile = Profile_conf.objects.filter(target_os=profile['target_os'],
                            compiler=profile['compiler'],
                            version=profile['version'],
                            name=profile['name'])
    if old_profile.count() != 0:
        context={'message':'A profile with same os/compiler/version/name already exists', 'nav2': 'active show'}
        return render(request, 'secuTool/test.html', context)


    new_profile = Profile_conf(uploader=profile['uploader'],
                                upload_time=timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S"),
                                name=profile['name'],
                                target_os=profile['target_os'],
                                compiler=profile['compiler'],
                                version=profile['version'],
                                flag=json.dumps(profile['flag']))
    new_profile.save()

    context = {"message":"New profile added successfully",
                "nav2":"active show"}

    return render(request, "secuTool/test.html", context)

def manageProfile(request):
    context = {}
    profiles = Profile_conf.objects.values()
    rows = []
    profile_dict = {}
    for profile in profiles:
        target_os, compiler, version = profile["target_os"], profile["compiler"], profile["version"]
        p_dict = {"target_os": target_os,
                    "compiler": compiler,
                    "version": version,
                    "name": profile["name"],
                    "flag": ", ".join(json.loads(profile['flag'])),
                    "date": profile['upload_time']
                    }
        rows.append(p_dict.copy())
        if target_os not in profile_dict:
            profile_dict[target_os] = {}
        if compiler not in profile_dict[target_os]:
            profile_dict[target_os][compiler] = []
        if version not in profile_dict[target_os][compiler]:
            profile_dict[target_os][compiler].append(version)

    context["rows"] = rows
    context['json_profiles'] = json.dumps(profile_dict)
    return render(request, "secuTool/manageProfile.html", context)

def manageCompiler(request):
    context = {}
    compilers = Compiler_conf.objects.values()
    rows = []
    compiler_dict = {}
    for compiler in compilers:
        target_os, target_compiler, version = compiler["target_os"], compiler["compiler"], compiler["version"]
        c_dict = {
            "target_os": target_os,
            'compiler': target_compiler,
            'version': version,
            'ip': compiler['ip'],
            'port': compiler['port'],
            'flag': "" if not compiler['flag'] else ", ".join(json.loads(compiler['flag'])),
        }
        rows.append(c_dict.copy())
        if target_os not in compiler_dict:
            compiler_dict[target_os] = {}
        if target_compiler not in compiler_dict[target_os]:
            compiler_dict[target_os][target_compiler] = []
        if version not in compiler_dict[target_os][target_compiler]:
            compiler_dict[target_os][target_compiler].append(version)

    context['rows'] = rows
    context['json_profiles'] = json.dumps(compiler_dict)
    return render(request, "secuTool/manageCompiler.html", context)

# ajax function to show content of compiler configuration
@csrf_exempt
def getCompiler(request):
    compiler = Compiler_conf.objects.get(target_os=request.POST['target_os'],
                                        compiler=request.POST['compiler'],
                                        version=request.POST['version'])

    res = {}
    for key in ['target_os', 'compiler', 'version', 'ip', 'port', 'flag', 'invoke_format']:
        res[key] = getattr(compiler, key)

    return HttpResponse(json.dumps(res), content_type="application/json ")

# ajax function to show content of profile
@csrf_exempt
def getProfile(request):
    profile = Profile_conf.objects.get(target_os=request.POST['target_os'],
                                            compiler=request.POST['compiler'],
                                            version=request.POST['version'],
                                            name=request.POST['name'])
    res = {}
    for key in ["target_os", "compiler", "version", "name", "flag", "uploader"]:
        res[key] = getattr(profile, key)
    res["upload_time"] = profile.upload_time
    return HttpResponse(json.dumps(res), content_type="application/json")

#TODO: duplicate detection in the case of 'save', should detect if the new model has the same key as one existing compiler
# better done though database key settings (construct unique compound key on the database, catch error, rather than doing the
# logic inside code)
@csrf_exempt
def updateCompiler(request):
    if request.POST['submit'] == 'save':    #update existing one
        old_compiler = Compiler_conf.objects.get(target_os=request.POST['old_target_os'],
                                    compiler=request.POST['old_compiler'],
                                    version=request.POST['old_version'])

        compiler = Compiler_conf.objects.filter(target_os=request.POST['target_os'],
                                    compiler=request.POST['compiler'],
                                    version=request.POST['version'])

        if (compiler.count() != 0 and compiler[0] != old_compiler):
            return render(
                request, "secuTool/test.html", {
                    'message':
                    'A compiler with the same OS/name/version already exists',
                    'nav2':
                    'active show'
                })

        compiler = old_compiler
        for key in ['target_os', 'compiler', 'version', 'ip', 'port', 'invoke_format']:
            setattr(compiler, key, request.POST[key])

        new_flag = map(lambda x: x.strip(), request.POST['flag'].splitlines())
        new_flag = list(filter(lambda x: x, new_flag))
        setattr(compiler, 'flag', json.dumps(new_flag))

        compiler.save()
        return render(request, "secuTool/test.html", {
            'message': 'Compiler successfully updated',
            'nav2': 'active show'
        })
    else:  #save as new
        compiler = Compiler_conf.objects.filter(target_os=request.POST['target_os'],
                                                compiler=request.POST['compiler'],
                                                version=request.POST['version'])
        if compiler.count() != 0:
            return render(
                request, "secuTool/test.html", {
                    "message":
                    "A compiler with the same OS/name/version already exists",
                    'nav2':
                    'active show'
                })

        d = {}
        for key in ['target_os', 'compiler', 'version', 'ip', 'port', 'invoke_format']:
            d[key] = request.POST[key]

        new_flag = map(lambda x: x.strip(), request.POST['flag'].splitlines())
        new_flag = list(filter(lambda x: x, new_flag))
        d['flag'] = json.dumps(new_flag)

        new_compiler = Compiler_conf(**d)
        new_compiler.save()
        return render(request, "secuTool/test.html", {
            'message': 'New compiler successfully saved',
            'nav2': 'active show'
        })


@csrf_exempt
def updateProfile(request):
    if request.POST['submit'] == 'save':    #update existing one
        old_profile = Profile_conf.objects.get(target_os=request.POST['old_target_os'],
                                    compiler=request.POST['old_compiler'],
                                    version=request.POST['old_version'],
                                    name=request.POST['old_name'])

        profile = Profile_conf.objects.filter(target_os=request.POST['target_os'],
                                    compiler=request.POST['compiler'],
                                    version=request.POST['version'],
                                    name=request.POST['name'])

        if (profile.count() != 0 and profile[0] != old_profile):
            return render(
                request, "secuTool/test.html", {
                    'message': 'A profile with the same OS/compiler/version/name already exists',
                    'nav2': 'active show'
                })

        profile = old_profile
        for key in ['target_os', 'compiler', 'version', 'name']:
            setattr(profile, key, request.POST[key])

        new_flag = map(lambda x: x.strip(), request.POST['flag'].splitlines())
        new_flag = list(filter(lambda x: x, new_flag))
        setattr(profile, 'flag', json.dumps(new_flag))

        profile.save()
        return render(request, "secuTool/test.html", {
            'message': 'Profile successfully updated',
            'nav2': 'active show'
        })
    else:  #save as new
        profile = Profile_conf.objects.filter(target_os=request.POST['target_os'],
                                                compiler=request.POST['compiler'],
                                                version=request.POST['version'],
                                                name=request.POST['name'])
        if profile.count() != 0:
            return render(
                request, "secuTool/test.html", {
                    "message":
                    "A profile with the same OS/compiler/version/name already exists"
                })

        d = {}
        for key in ['target_os', 'compiler', 'version', 'name', 'uploader']:
            d[key] = request.POST[key]

        d['upload_time'] = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")

        new_flag = map(lambda x: x.strip(), request.POST['flag'].splitlines())
        new_flag = list(filter(lambda x: x, new_flag))
        d['flag'] = json.dumps(new_flag)

        new_profile = Profile_conf(**d)
        new_profile.save()
        return render(request, "secuTool/test.html", {
            'message': 'New profile successfully saved',
            'nav2': 'active show'
        })


@csrf_exempt
def deleteCompiler(request):
    compiler_to_delete = Compiler_conf.objects.get(target_os=request.POST['target_os'],
                                    compiler=request.POST['compiler'],
                                    version=request.POST['version'])
    compiler_to_delete.delete()
    return render(request, "secuTool/test.html", {'message':'Compiler successfully deleted', 'nav2': 'active show'})

@csrf_exempt
def deleteProfile(request):
    profile_to_delete = Profile_conf.objects.get(target_os=request.POST['target_os'],
                                                compiler=request.POST['compiler'],
                                                version=request.POST['version'],
                                                name=request.POST['name'])
    profile_to_delete.delete()
    return render(request, "secuTool/test.html", {'message':'Profile successfully deleted', 'nav2': 'active show'})