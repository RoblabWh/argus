import os    
import sys

from exif_header import ExifHeader

class PathReader:
    @staticmethod
    def read_path(path, start_file_types, ends_file_types, sort):
        read_paths = list()
        #print("-Loading " + str(len(os.listdir(path))) + " file paths...")
        for file in sorted(os.listdir(path)):
            if file.startswith(start_file_types) and file.endswith(ends_file_types): 
                read_paths.append(os.path.join(path, file))
        ret_paths = read_paths
        #read_paths.sort(key=os.path.getctime)
        
        if sort:
            print("-Sorting " + str(len(read_paths)) +  " images by creation time...")
            unsorted_list = list()
            for path in read_paths:
                creation_time = ExifHeader(path).get_creation_time()
                #print(creation_time)
                unsorted_list.append([path, creation_time])        
            sorted_list = sorted(unsorted_list, key=lambda x:x[1])
            sorted_paths = ([x[0] for x in sorted_list])
            ret_paths = sorted_paths
        return ret_paths
