# TODO
# * Cleanup code, remove extraneous bits from tutorial code
# * Put UbuWeb class file in correct place
# * Write code to check to latest DB
# * Be more careful with DB file download and writing

import sys
import xbmc, xbmcgui, xbmcplugin
import urllib, urllib2
import xbmcaddon

import os

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

import hmac
try:
    import hashlib.sha1 as sha1
except:
    import sha as sha1

import BeautifulSoup as BS

import UbuWeb

__addon__ = xbmcaddon.Addon(id='plugin.video.ubuweb')
__info__ = __addon__.getAddonInfo
__icon__ = __info__('icon')
__fanart__ = __info__('fanart')
__plugin__ = __info__('name')
__version__ = __info__('version')
__path__ = __info__('path')
__cachedir__ = __info__('profile')

pluginpath = __addon__.getAddonInfo('path')

# parameter keys
PARAMETER_KEY_MODE = "mode"

# URL of db file
DB_FILE_URL = "http://zeitkunst.org/media/code/plugin.video.ubuweb/UbuWeb.db"

# URL of update info
UPDATE_URL = "http://zeitkunst.org/media/code/plugin.video.ubuweb/last_updated"

# Local path of db file
DB_FILE_PATH = os.path.join(xbmc.translatePath(__cachedir__))
DB_FILE_NAME = "UbuWeb.db"

# plugin handle
handle = int(sys.argv[1])

class Main:
    def __init__(self):
        if not sys.argv[2]:
            ok = self.showRootMenu()
        else:
            params = self.parametersStringToDict(sys.argv[2])
            mode = int(params.get(PARAMETER_KEY_MODE, "0"))
            ok = self.showByNameID(mode)

    def parametersStringToDict(self, parameters):
        ''' Convert parameters encoded in a URL to a dict. '''
        paramDict = {}
        if parameters:
            paramPairs = parameters[1:].split("&")
            for paramsPair in paramPairs:
                paramSplits = paramsPair.split('=')
                if (len(paramSplits)) == 2:
                    paramDict[paramSplits[0]] = paramSplits[1]
        return paramDict

    def addDirectoryItem(self, name, isFolder=True, parameters={}):
        ''' Add a list item to the XBMC UI.'''
        li = xbmcgui.ListItem(name)
        url = sys.argv[0] + '?' + urllib.urlencode(parameters)
        return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=li, isFolder=isFolder)
    
        
    def showRootMenu(self):
        ''' Show the plugin root menu. '''
        u = UbuWeb.UbuWebFilm(dbPath = DB_FILE_PATH, dbName = DB_FILE_NAME, dbURL = DB_FILE_URL, updateURL = UPDATE_URL)
        
        names = u.getNames()
        
        print names
        c = u.db.cursor()
        for n in c.execute("select * from names"):
            print n
        for name in names:
            self.addDirectoryItem(name=name["name"], parameters={ PARAMETER_KEY_MODE: name["nid"]}, isFolder=True)
    
        xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
        
    def showByNameID(self, nameID):
        u = UbuWeb.UbuWebFilm(dbPath = DB_FILE_PATH, dbName = DB_FILE_NAME, dbURL = DB_FILE_URL)
        films = u.getFilmsByNameID(nameID)
        for film in films:
            title = film["filmTitle"]
            link = film["filmLink"]
            listitem = xbmcgui.ListItem(title)
            listitem.setProperty("IsPlayable", "true")
            listitem.setInfo(type="video",
                             infoLabels = {"title": title,
                                           "plot": film["comments"]})
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), link, listitem, isFolder=False)
        xbmcplugin.endOfDirectory(handle=handle, succeeded=True)


if __name__ == "__main__":
    Main()
