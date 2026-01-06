import os
from pymongo import MongoClient
import numpy as np
from adios2 import FileReader


## to run:
# brew services start mongodb/brew/mongodb-community@7.0
# brew services stop mongodb-community@7.0
# brew services list

# schema

SCHEMA = '''
"campaign_path": campaign_path,
"file": file,
"variable_name": var,
"variable_path": varpath,
"variable_type": var_type,
"variable_location": var_location,
"metadata": metadata,
"producer": sim,exper,analysis, etc.

----- Optional values.
"visualization_name": str or None
"movie_cache": key or None
'''

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "catnip_campaigns")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "campaign_entries")


def get_collection():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB][MONGO_COLLECTION]

def clear_collection():
    """Delete all documents in the configured collection."""
    collection = get_collection()
    collection.delete_many({})

def _to_simple_string(input:str) -> str:
    return input.translate(str.maketrans('', '', '"'))

def extract_file_var(input:str) -> tuple[str,str, str,str]:
    parts = input.split('/')
    if len(parts) < 2 :
        raise ValueError(f"Invalid file variable format: {input}")
    producer = parts[0]
    varname = parts[-1]
    filename = parts[-2]
    varpath = '/'.join(parts[0:-1])
    return (varname, filename, varpath, producer)

def extract_file_var_img(input:str) -> tuple[str,str, str,str]:
    parts = input.split('/')
    if len(parts) < 4 :
        raise ValueError(f"Invalid image variable format: {input}")
    producer = parts[0]
    varname = parts[3]
    filename = parts[2]
    varpath = input
    return (varname, filename, varpath, producer)


def get_visualization_name(input:str) -> str :
    parts = input.split('/')
    if 'images' in parts :
        idx = parts.index('images')
        return parts[idx+1]
    else :
        return ''

def parse_campaign(campaign_path:str) :
    collection = get_collection()
    with FileReader(campaign_path) as fr:
        vars_dict  = fr.available_variables()   # Dict[str, Dict[str,str]]
        attrs_dict = fr.available_attributes()  # Dict[str, Dict[str,Any]]
        #print(attrs_dict)
        CNT = -1
        for varname, varinfo in vars_dict.items() :
            CNT = CNT + 1
            type_key = varname + '/__dataset_type__'
            loc_key = varname + '/__dataset_location__'
            var_type = 'variable'
            var_location = 'local'
            if type_key in attrs_dict.keys() :
                var_type = _to_simple_string(attrs_dict[type_key]['Value'])
            if loc_key in attrs_dict.keys() :
                var_location = _to_simple_string(attrs_dict[loc_key]['Value'])

            if var_type == 'variable' :
                var, file, varpath, producer = extract_file_var(varname)
            else :
                var, file, varpath, producer = extract_file_var_img(varname)

            metadata = varinfo

            document = None
            if var_type == 'image' :
                visualization_name = get_visualization_name(varname)
                document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "variable_name": var,
                    "visualization_name": visualization_name,
                    "variable_path": varpath,
                    "variable_type": var_type,
                    "producer": producer,
                    "variable_location": var_location,
                    "metadata": metadata,
                    "movie_cache": 1
                }
                collection.insert_one(document)
            else:
                print('********** varType: ', var, var_type, varpath, var_location)

                document = {
                    "campaign_path": campaign_path,
                    "file": file,
                    "variable_name": var,
                    "variable_path": varpath,
                    "variable_type": var_type,
                    "producer": producer,
                    "variable_location": var_location,
                    "metadata": metadata,
                }
                collection.insert_one(document)


clear_collection()
#parse_campaign("one_file.aca")
parse_campaign("kh.aca")

collection = get_collection()

queryVar = {'variable_name': 'omega', 'variable_type':'variable'}
queryImg = {'variable_name': 'omega', 'variable_type':'image'}
visNames = collection.distinct('visualization_name', queryImg)

producersImg = collection.distinct('producer', queryImg)
producersVar = collection.distinct('producer', queryVar)
# these should be the same!

print('Visualization Names for omega image: ', visNames)
#get all of the images for a var/producer/visname.
queryVarImgs = {'variable_name': 'omega', 'variable_type':'image', 'producer': producersImg[1], 'visualization_name': visNames[0]}
coll = collection.find(queryVarImgs)
for doc in coll:
    print(doc['variable_path'])

shit()

allProducers = collection.distinct('producer')
print('Producers: ', allProducers)
allVarNames = collection.distinct('variable_name')
print('Variable Names: ', allVarNames)
for var in allVarNames:
    print('---- Variable: ', var)
    query = {'variable_name': var, 'variable_type':'image'}
    visNames = collection.distinct('visualization_name', query)
    print('   Visualization Names: ', visNames)
    varProducers = collection.distinct('producer', query)
    print('   Producers: ', varProducers)

    query = {'variable_name': var, 'variable_type':'image', 'producer': varProducers[0]}
    cursor = collection.find(query)
    #for doc in cursor:
    #    print(doc)
    #    shit()
    print('---------------------\n\n')


shit()

#query = {'variable_type': 'variable', 'file': 'data.bp', 'variable_name':'var0'}
query = {'movie_cache': 1, 'file': 'data.bp', 'variable_name':'var0'}
query = {'variable_type':'variable', }
cursor = collection.find(query)
for doc in cursor:
    print(doc, '\n\n')
    #print(doc['variable_name'], doc['metadata'])


#print('\n\nHas movie')
#X = list(collection.find({"movie_cache": {"$exists": True}}))
#print(X[0])