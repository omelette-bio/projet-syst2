import os, argparse


def list_files(path, recursive=False):
   if not os.path.isdir(path):
      return([path])
   else:
      os.chdir(path)
      directories = [path]
      files = []

      while len(directories) > 0:
         for i in os.listdir(os.getcwd()):
            if i[0] == "." or i[0] == "_" or i[0] == "~":
               pass
            elif os.path.isdir(i) and recursive:
               directories.append(os.path.join(os.getcwd()) + "/" + i)
            elif os.path.isfile(i):
               files.append(i)
         if recursive:
            os.chdir(directories.pop())
         else:
            directories.pop()
      return(files)

if __name__ == "__main__":
   parser = argparse.ArgumentParser()
   parser.add_argument("path", help="path to list files from")
   args = parser.parse_args()
   
   
   print(list_files(args.path, True))
   print(list_files(args.path))