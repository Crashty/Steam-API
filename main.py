from aiohttp import ClientSession, ClientTimeout, ClientConnectionError
import requests
import json
import asyncio
from tqdm import tqdm
import math
import time


key = None
nested_sleep = 25
retries = 0
max_retries = 4

try:
    with open("key.txt","r") as c:
        key = c.read()
except:
    print("Could not retrieve steam-api key. Ensure key.txt exists.")
    exit(1)


class failure:
    def __init__(self, url):
        self.url = url

def steam_request(interface, method, version, params=None, raw=False):
    url = f"http://api.steampowered.com/{interface}/{method}/v{version}/?key={key}&format=json{params}"
    if raw: return url
    
    response = requests.get(url)
    return response

async def a_steam_request(session: ClientSession, url, bar):
    response = await session.get(url)
    bar.update(1)
    return response
    
    
def download_apps():
    print("Downloading app list..")
    response = steam_request("ISteamApps","GetAppList",2)
    response_j = response.json()

    with open("applist.json","w",encoding="utf-8") as f:
        f.write(json.dumps(response_j,indent=4))

    print("Download complete, 'applist.json' saved")

def load_apps():
    try:
        with open("applist.json", "r") as f:
            applist = json.load(f)
            return applist

    except Exception as e:
        print(e)


def app_getid(name):
    apps = load_apps()
    
    for app in apps["applist"]["apps"]:
        if app["name"] == name:
            return app["appid"]
    
    return None

def app_player_count(appid):
    response = steam_request("ISteamUserStats","GetNumberOfCurrentPlayers",1,params=f"&appid={appid}")
    response_j = json.loads(response.text)
    result = response_j["response"]["result"]
    if result != 1: return 0
    return response_j["response"]["player_count"]


async def update_tasks(repeat):
    print(f"{len(repeat)} errors detected, retrying..")
    new_tasks = []
    results = []
    repeat_2 = []
    global retries
    retries += 1

    for err in repeat:
        new_tasks.append(err[1].url)



    print(f"Resending {len(new_tasks)} requests..")
    pbar = tqdm(total=len(new_tasks),unit="request")
    async with ClientSession(timeout=ClientTimeout(total=None)) as session:
        results = await asyncio.gather(*[a_steam_request(session, url, pbar) for url in new_tasks], return_exceptions=True)
        pbar.close()

    old_data = {}



    print("Reading output..")
    with open("output.json","r", encoding="utf-8") as f:
        old_data = json.load(f)

    print("Adjusting results..")
    pbar = tqdm(total=len(results),unit="result")
    for i, result in enumerate(results):
        pbar.update(1)
        k = repeat[i][0]

        if isinstance(result,ClientConnectionError): 
            url = steam_request("ISteamUserStats","GetNumberOfCurrentPlayers",1,params=f"&appid={appid}",raw=True)
            repeat_2.append((k,failure(url)))
            print("\noops")
            continue
        
        
        status = result.status
        name = old_data["apps"][k]["name"]
        appid = old_data["apps"][k]["appid"]

        if status == 200:
            result_j = await result.json()
            old_data["apps"][k] = {"order":k,"name":name,"appid":appid,"players":result_j["response"]["player_count"]}
        else:
            txt = await result.text()
            url = str(result.url)
            old_data["apps"][k] = {"order":k,"name":name,"appid":appid,"error": txt,"url":url}
            if "429 Too Many Requests" in txt or "You don't have permission to access" in txt:
                repeat_2.append((k,result))
    pbar.close()
    print("Writing new results..")
    with open(f"output_v{1+retries}.json","w",encoding="utf-8") as f:
        json.dump(old_data,f,indent=4,ensure_ascii=False)

    print(f"Done reworking with {len(repeat_2)} errors. {math.floor((1-len(repeat_2)/len(repeat))*100)}% of errors fixed")

    if len(repeat_2):

        if retries != max_retries:
            print(f"Retrying in {nested_sleep} seconds..")
            time.sleep(nested_sleep)
            await update_tasks(repeat_2)
        else:
            print(f"Max retries reached.. Terminating execution with {len(repeat_2)} errors")



async def process_results(results, apps):
    data = {"apps":[]}
    repeat = []

    
    with open("output.json","w", encoding="utf-8") as f:


        print("Synchronizing results to apps..")
        pbar = tqdm(total = len(results), unit = "result")

        for k, result in enumerate(results):
            pbar.update(1)

            
            name = apps["applist"]["apps"][k]["name"]
            appid = apps["applist"]["apps"][k]["appid"]

            if isinstance(result,ClientConnectionError): 
                url = steam_request("ISteamUserStats","GetNumberOfCurrentPlayers",1,params=f"&appid={appid}",raw=True)
                repeat.append((k,failure(url)))
                data["apps"].append({"order":k,"error":str(result)})
                print("\noops")
                continue


            status = result.status
            
            if status == 200:
                result_j = await result.json()
                data["apps"].append({"order":k,"name":name,"appid":appid,"players":result_j["response"]["player_count"]})
            else:
                txt = await result.text()
                url = str(result.url)
                data["apps"].append({"order":k,"name":name,"appid":appid,"error": txt,"url":url})
                if "429 Too Many Requests" in txt or "You don't have permission to access" in txt:
                    repeat.append((k,result))

        
        pbar.close()

        print("Writing results to file..")
        json.dump(data,f,indent=4,ensure_ascii=False)

    if len(repeat):
        with open("err.txt","w",encoding="utf-8") as ff:
            for err in repeat:
                ff.write(f"{err}\n")

        await update_tasks(repeat)

        




async def apps_player_count(max=None):

    #download_apps()
    apps = load_apps()
    current = 0
    tasks = []

    for app in apps["applist"]["apps"]:
        appid = app["appid"]
        tasks.append(steam_request("ISteamUserStats","GetNumberOfCurrentPlayers",1,params=f"&appid={appid}",raw=True))

        if max:
            current += 1
            if current >= max: 
                break

    print(f"Sending requests for {len(tasks)} apps..")
    pbar = tqdm(total=len(tasks),unit="request")


    async with ClientSession(timeout=ClientTimeout(total=None)) as session:
        results = await asyncio.gather(*[a_steam_request(session, url, pbar) for url in tasks], return_exceptions=True)
        pbar.close()

        await process_results(results, apps)

t1 = time.time() 
asyncio.run(apps_player_count())
print(f"Job's done! {math.floor(time.time()-t1)} seconds and {retries} retries!")