#! /usr/bin/python3

import options, sender, message, generator, server
import sys, os, signal

args = options.parsing()

if args.help:
   options.help()
   sys.exit(0)

if args.list_only: 
   options.listing(generator.sort_by_path(sender.list_files(args.source, args)))
   sys.exit(0)

def handler(signum, frame):
   global pipes
   print("Interrupted, exiting...", file=sys.stderr)
   for fd in pipes:
      os.close(fd)
   sys.exit(20)

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGUSR1, handler)

# connect to server with pipe
# fork to create a child process which will be the server

fdr1, fdw1 = os.pipe()
fdr2, fdw2 = os.pipe()

#server process, read on fdr1, write on fdw2
if os.fork() == 0:
   # close unused pipes
   os.close(fdw1)
   os.close(fdr2)
   
   pipes = [fdr1, fdw2]
   
   # create the list of files at the destination
   os.chdir(args.destination)
   destination_files = generator.sort_by_path(sender.list_files(".", args))
   
   # receive the list of files to send
   (tag,v) = message.receive(fdr1)
   
   files_to_send = generator.sort_by_path(v)
   # generator to send files
   if os.fork() == 0:
      # create the list of files to send, modify and delete
      send, modify, delete = generator.compare(files_to_send, destination_files, len(args.source))
      
      state = "send"
      # we send some requests to the client, if it's not empty
      if len(send) > 0:
         message.send(fdw2, "send", send)

      if len(modify) > 0:
         message.send(fdw2, "modify", modify)
      
      if len(delete) > 0:
         message.send(fdw2, "delete", delete)
      
      if len(send) == 0 and len(modify) == 0 and len(delete) == 0:
         message.send(fdw2, "end", "No files to send/modify/delete")
         state = "end"
      
      if state == "send":
         message.send(fdw2, "end", "No more to send/modify/delete")
         state = "end"
      
      
      os.close(fdw2)
      os.close(fdr1)
      sys.exit(0)
   
   os.wait()
   
   # now receive the files to copy and the files to modify
   
   while True:
      (tag,v) = message.receive(fdr1)
      if tag == "timeout":
         print("Timeout, exiting...", file=sys.stderr)
         os.close(fdw2)
         os.close(fdr1)
         sys.exit(21)
      
      if type(v) == tuple:
         if args.perms:
            file, folder, data, perms = v
         else:
            file, folder, data = v
            perms = 33204
         
         if tag == "sendfile":
            #check if the folder exists, if not create it
            if folder != "":
               if not os.path.isdir(folder):
                  os.makedirs(folder)
                  if args.verbose > 0:
                     print(f"Creating folder {folder}", file=sys.stderr)
            
            #create the file
            file = os.path.join(folder, os.path.basename(file))
            currentfile = os.open(file, os.O_CREAT | os.O_WRONLY)
            
            if args.perms:
               if args.verbose > 0:
                  print(f"Changing permissions of {file} to {perms}", file=sys.stderr)
               os.chmod(file, perms)
            
            if args.verbose > 0:
               print(f"Receiving {file}...", file=sys.stderr)
            
            #change the standard output to the file
            
            os.dup2(currentfile, 1)
            
            #write the data
            
            os.write(1, data)
            os.close(currentfile)

         if tag == "modifyfile":
            #check if the folder exists, if not create it
            if folder != "":
               if not os.path.isdir(folder):
                  os.makedirs(folder)
                  if args.verbose > 0:
                     print(f"Creating folder {folder}", file=sys.stderr)
            
            #create the file
            file = os.path.join(folder, os.path.basename(file))
            currentfile = os.open(file, os.O_CREAT | os.O_WRONLY)
            
            if args.perms:
               if args.verbose > 0:
                  print(f"Changing permissions of {file} to {perms}", file=sys.stderr)
               os.chmod(file, perms)
            
            if args.verbose > 0:
               print(f"Receiving {file}...", file=sys.stderr)
            
            #change the standard output to the file
            
            os.dup2(currentfile, 1)
            
            #write the data
            
            os.write(1, data)
            os.close(currentfile)
         
      elif tag == "endfile" and args.verbose > 0:
         print(f"Done", file=sys.stderr)
         print("")
         
      elif tag == "end":
         os.dup2(1, 1)
         break
      
   
   os.close(fdw2)
   os.close(fdr1)
   sys.exit(0)


#client process, read on fdr2, write on fdw1
if os.fork() == 0:
   # close the unnecessary pipes
   os.close(fdw2)
   os.close(fdr1)
   pipes = [fdr2, fdw1]
   
   # create the list of files at the source
   files = sender.list_files(args.source, args)
   # and send it to the server
   message.send(fdw1, "data", files)
   # wait for request messages from the generator
   tag = ""
   send_list = []
   modify_list = []
   
   while tag != "end":
      
      (tag, v) = message.receive(fdr2)
      
      if args.verbose > 0:
         print(f"{tag} : {v}")
         print("")
         
      if tag == "send":
         send_list = v
      
      elif tag == "modify":
         modify_list = v
   
      elif tag == "delete" and args.delete:
         server.order_list_delete(v)
         for file in v:
            os.remove(os.path.join(args.destination, file))
            # if the folder is empty, delete it
            if os.path.dirname(file) != "":
               if not os.listdir(os.path.join(args.destination,os.path.dirname(file))):
                  os.rmdir(os.path.join(args.destination,os.path.dirname(file)))
   
   # now for each file to send, we send the name, his path and the content
   if send_list != []:
      
      for file in send_list:
         
         if len(args.source) > 1:
            file = '/'.join(file.split('/')[1:])
         
         full_path = os.path.join(files[file][0], file)
         
         if args.verbose > 0:
            print(f"Sending : {full_path}")
         
         try:
            sending_file = os.open(full_path, os.O_RDONLY)
         except:
            if args.verbose > 0:
               print(f"Error while opening {file}", file=sys.stderr)
            os.close(fdw1)
            os.close(fdr2)
            sys.exit(23)
            
         if args.verbose > 0:
            print(f"Reading...")
            print("")
            
         # read the file and send it, in multiple parts if size > 16 Mo
         while True:
            try:
               data = os.read(sending_file, 16*1024*1024)
            except:
               if args.verbose > 0:
                  print(f"Error while reading {file}", file=sys.stderr)
               os.close(sending_file)
               os.close(fdw1)
               os.close(fdr2)
               sys.exit(11)
            
            folder = ""
            
            if len(args.source) > 1:
               if os.path.dirname(file) == "":
                  folder = os.path.basename(files[file][0])
               
               else:
                  folder = os.path.join(os.path.basename(files[file][0]), os.path.dirname(file))
            
            else:
               if os.path.dirname(file) != "":
                  folder = os.path.dirname(file)
            
            message.send(fdw1, "sendfile", (file, folder, data, files[file][3]))
            
            # send "endfile" if there the file has been read entirely
            if len(data) < 16*1024*1024:
               message.send(fdw1, "endfile", "endfile")
               break
         
         os.close(sending_file)
      
      message.send(fdw1, "end", "end")
      
   if modify_list != []:
      
      for file in modify_list:
         
         if len(args.source) > 1:
            file = '/'.join(file.split('/')[1:])
         
         full_path = os.path.join(files[file][0], file)
         
         if args.verbose > 0:
            print(f"Sending : {full_path}")
            
         sending_file = os.open(full_path, os.O_RDONLY)
         
         if args.verbose > 0:
            print(f"Reading...")
            print("")
            
         # read the file and send it, in multiple parts if size > 16 Mo
         while True:
            data = os.read(sending_file, 16*1024*1024)
            
            folder = ""
            
            if len(args.source) > 1:
               if os.path.dirname(file) == "":
                  folder = os.path.basename(files[file][0])
               
               else:
                  folder = os.path.join(os.path.basename(files[file][0]), os.path.dirname(file))
            
            else:
               if os.path.dirname(file) != "":
                  folder = os.path.dirname(file)
                  
            message.send(fdw1, "modifyfile", (file, folder, data, files[file][3]))
            
            # send "endfile" if there the file has been read entirely
            if len(data) < 16*1024*1024:
               message.send(fdw1, "endfile", "endfile")
               break
         
         os.close(sending_file)
      
      message.send(fdw1, "end", "end")
   
   if modify_list == [] and send_list == []:
      message.send(fdw1, "end", "end")
   
   os.close(fdw1)
   os.close(fdr2)
   sys.exit(0)

sys.exit(0)