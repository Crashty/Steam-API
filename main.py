from aiohttp import ClientSession, ClientTimeout, ClientConnectionError
import requests
import json
import asyncio
from tqdm import tqdm


key = "12D3DF35DFCF4DA85DA50C945EEA447F"

pbar = None
invalid = 0

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

async def process_results(results, apps):
            print("Collecting synchronization apps..")
            data = {"apps":[]}
            repeat = [()]

            print("Writing output data to file..")
            with open("output.json","w", encoding="utf-8") as f:
                for k, result in enumerate(results):

                    if isinstance(result,ClientConnectionError): 
                        print("oops")
                        repeat.append((k,result))
                        continue

                    status = result.status
                    name = apps["applist"]["apps"][k]["name"]
                    appid = apps["applist"]["apps"][k]["appid"]

                    if status == 200:
                        result_j = await result.json()
                        data["apps"].append({"name":name,"appid":appid,"players":result_j["response"]["player_count"]})
                    else:
                        data["apps"].append({"name":name,"appid":appid,"error": await result.text(),"url":str(result.url)})
                        repeat.append((k,result))
                

                    
                json.dump(data,f,indent=4,ensure_ascii=False)

                with open("err.txt","w",encoding="utf-8") as ff:
                    for err in repeat:
                        ff.write(f"{err}\n")


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
        print("Done retrieving app info..")

        await process_results(results, apps)

asyncio.run(apps_player_count(5000))
