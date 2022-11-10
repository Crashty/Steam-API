from aiohttp import ClientSession, ClientTimeout, ClientConnectionError
import requests
import json
import asyncio
from tqdm import tqdm


key = ""

try:
    with open("key.txt","r") as f:
        key = f.read()
except:
    print("Could not retrieve steam-api key. Ensure key.txt exists.")

pbar = None

def steam_request(interface, method, version, params=None, raw=False):
    url = f"http://api.steampowered.com/{interface}/{method}/v{version}/?key={key}&format=json{params}"
    if raw: return url
    
    response = requests.get(url)
    return response

async def a_steam_request(session: ClientSession, url):
    response = await session.get(url)

    pbar.update(1)
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

def app_player_count(appid, raw=False):
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

    for err in repeat:
        new_tasks.append(err[1])

    pbar = tqdm(total=len(new_tasks),unit="request")

    async with ClientSession(timeout=ClientTimeout(total=None)) as session:
        results = await asyncio.gather(*[a_steam_request(session, url) for url in new_tasks], return_exceptions=True)
        pbar.close()

    old_data = None

    with open("output.json","r",encoding="utf-8") as f:
        old_data = json.loads(f.read())


    for result in tqdm(results):

        k = None

        for app in old_data["apps"]:
            for err in repeat:
                if app["order"] == err[0]:
                    k = err[0]

        if isinstance(result,ClientConnectionError): 
            print("oops")
            repeat_2.append((k,result))
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

        with open("output_v2.json","w",encoding="utf-8") as f:
            print("Writing results to file..")
            json.dump(old_data,f,indent=4,ensure_ascii=False)

        
    print(f"Done with {len(repeat_2)} errors")




async def process_results(results, apps):
    data = {"apps":[]}
    repeat = []

    
    with open("output.json","w", encoding="utf-8") as f:


        print("Synchronizing results to apps..")
        pbar = tqdm(total = len(results), unit = "result")

        for k, result in enumerate(results):

            pbar.update(1)
            if isinstance(result,ClientConnectionError): 
                print("oops")
                repeat.append((k,result))
                data["apps"].append({"order":k,"error":str(result)})
                continue

            status = result.status
            name = apps["applist"]["apps"][k]["name"]
            appid = apps["applist"]["apps"][k]["appid"]
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
    global pbar
    pbar = tqdm(total=len(tasks),unit="request")


    async with ClientSession(timeout=ClientTimeout(total=None)) as session:
        results = await asyncio.gather(*[a_steam_request(session, url) for url in tasks], return_exceptions=True)
        pbar.close()

        await process_results(results, apps)

asyncio.run(apps_player_count(10000))
print("Done")