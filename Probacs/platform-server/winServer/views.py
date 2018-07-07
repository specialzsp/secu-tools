
import os, tempfile, zipfile,tarfile, time,sys
from datetime import datetime
from wsgiref.util import FileWrapper
from django.shortcuts import render
from winServer.forms import *
from winServer.models import *
from django.core.files import File 
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests    #need pip install requests
from subprocess import Popen, PIPE
# from multiprocessing import Process

# hostserver = "http://192.168.27.131:8000/" #ip/port of the host server
# hostserver = "http://172.16.165.125:8000/" #ip/port of the host server
rootDir = 'Compilation_tasks'
hostserver = "" #ip/port of the host server on virtualbox
os_name = os.name
if os_name == 'nt':
    delimit = "\\"
else:
    delimit = "/"


@csrf_exempt
def execute(request):
	#create working dir for this compilation task
	taskFolder = request.POST['taskid']
	print("id: "+taskFolder)
	#timestr = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
	os.system("mkdir "+rootDir+delimit+taskFolder)
	print('order received')
	#save file in task folder
	filename = request.FILES['file'].name
	# host_ip = request.META['REMOTE_ADDR']
	# host_port = request.META['SERVER_PORT']
	# hostserver = "http://"+host_ip+":"+host_port+"/"
	# print(host_ip+" "+host_port)
	hostserver = request.POST['host_ip']+"/"
	src_dir = 'src'
	if not os.path.exists(src_dir):
		os.mkdir(src_dir)

	with open(rootDir+delimit+taskFolder+delimit+filename,'wb+') as dest:
		for chunk in request.FILES['file'].chunks():
			dest.write(chunk)
	if os_name == 'nt':
		tar = r'"C:\Program Files (x86)\GnuWin32\bin\tar.exe"'
	else:
		tar = "tar"
	os.system(tar+" "+"xvf "+ rootDir+delimit+taskFolder+delimit+filename)

	print(request.FILES['file'])

	############################################
	# compilation work
	srcpath = src_dir+delimit+request.POST['Srcname']
	print(srcpath)
	compileDir = rootDir+delimit+taskFolder+delimit+'secu_compile_platform'
	os.mkdir(compileDir)
	# compilation start here, store executables and logs
	# into compileDir
	cl = None
	if 'env' in request.POST and request.POST['env'] != None:
		cl = request.POST['env'].replace("_",' ')
	# compile(taskFolder, request.POST['target_os'], request.POST['compiler'], request.POST['version'],
	# 	srcpath, compileDir, request.POST['command'], request.POST['flags'],cl)
	# make compilation async
	# p = Process(target=sub_process,args=(request.POST,taskFolder,srcpath,compileDir,cl,src_dir))
	# p.start()
	# print("python make_compilation.py "+srcpath+ " "+compileDir+" "+request.POST['command']+" "+request.POST['flags'])
	# cl = r'"C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvars64.bat"'
	if cl == None:
		os.system("python make_compilation.py "+taskFolder+" "+
			request.POST['target_os']+" "+request.POST['compiler']+" "+request.POST['version']+" "+
			srcpath+ " "+compileDir+" "+request.POST['command']+" "+request.POST['flags']+" "+hostserver)
	else:
		os.system(cl+"&& python make_compilation.py "+taskFolder+" "+
			request.POST['target_os']+" "+request.POST['compiler']+" "+request.POST['version']+" "+
			srcpath+ " "+compileDir+" "+request.POST['command']+" "+request.POST['flags']+" "+hostserver)

	############################################
	# send back exe archive to host by http request
	responseFromHost,tmpzip = sendBackExe(taskFolder, hostserver) # test purpose, replace hellomake later
	##clear environment
	if os_name == 'nt':
		os.system("del /f "+src_dir +" /Q") 
		os.system("del /f *.tgz")
	else:
		os.system("rm -rf "+src_dir)
		os.system("rm *.obj")
		os.system("rm *.tgz")
	response = HttpResponse()
	print("send back request")
	return response




# create zip file containing exe and log, then send to host
# delete zip file after sending to host
def sendBackExe(folder,hostserver):
	#create a zip file first
	print("send back exe")
	timestr = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
	new_name = "exe_"+timestr+".tgz"
	exe_folderPath = rootDir+delimit+folder+delimit+'secu_compile_platform'
	with tarfile.open(new_name, "w:gz") as tar:
		tar.add(exe_folderPath, arcname=os.path.basename(exe_folderPath))
	compressed_dir = open(new_name,'rb')
	#form http request
	files = {'file':(new_name,compressed_dir)}
	print(hostserver)
	url = hostserver+'saveExe';
	response = requests.post(url, files = files,data={'taskid': folder})
	print("response received from host")
	return response,new_name

# test only, not fully deployed
def retJson(request):
	print('retJson called')
	response = {}
	response['message'] = "receive request successfully !"
	return HttpResponse(json.dumps(response),  content_type="application/json")