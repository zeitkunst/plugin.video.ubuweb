import htmlentitydefs, os, random, re, time, urllib2

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

# From: http://effbot.org/zone/re-sub.htm#unescape-html
def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)

class UbuWebFilm(object):
    BASE = "http://www.ubu.com/film/"
    fileRE = re.compile("'file=(.*)'")
    swfRE = re.compile("SWFObject")
    JUNK_THRESHOLD = 25

    # os.path.join(xbmc.translatePath(pluginpath),'resources','cache','UbuWeb.db')

    def __init__(self, dbPath = ".", dbName = "UbuWeb.db", dbURL = None, updateURL = None, init=True, xbmc = True):
        # TODO
        # Make option to check status of database
        self.dbPath = os.path.join(dbPath, dbName)
        self.dbURL = dbURL
        self.updateURL = updateURL

        if init:
            if not os.path.exists(dbPath):
                os.makedirs(dbPath)
                if dbURL is not None:
                    self.getDB(self.dbURL)

                    self.db = sqlite.connect(self.dbPath)
                    self.db.text_factory = str
                else:
                    self.db = sqlite.connect(self.dbPath)
                    self.db.text_factory = str
                    self.createUbuWebDB()
                    self.parseFilmListingPage(numLinks = None, startLink = 16)
            else:
                self.db = sqlite.connect(self.dbPath)
                self.db.text_factory = str
                if self.updateURL is not None:
                    self.checkDB()

    def createUbuWebDB(self):
        c = self.db.cursor()
        c.execute('''CREATE TABLE Status(
            sid INTEGER PRIMARY KEY,
            lastUpdated float)
            ''')
        c.execute('''CREATE TABLE Names(
            nid INTEGER PRIMARY KEY,
            name TEXT,
            hash TEXT,
            link TEXT,
            comments TEXT)
            ''')
        c.execute('''CREATE TABLE Films(
            fid INTEGER PRIMARY KEY,
            hash TEXT,
            title TEXT,
            link TEXT,
            originalLink TEXT,
            comments TEXT)
            ''')
            
        self.db.commit()
        c.close()

    def checkDB(self):
        if self.updateURL is not None:
            data = self.doRequest(self.updateURL)
            lastUpdated = float(data.strip())

            if (lastUpdated > self.getLastUpdated()):
                print "Updating UbuWeb Film database from %s" % self.updateURL
                self.getDB(self.dbURL)

    def getDB(self, dbURL):
        if dbURL is not None:
            dbData = self.doRequest(dbURL)
            with open(self.dbPath, "wb") as fp:
                fp.write(dbData)

    def parseFilmListingPage(self, filmPage = "http://www.ubu.com/film", numLinks = 10, startLink = 1):
        # Open Ubuweb film page
        req = urllib2.Request("http://www.ubu.com/film/")
        response = urllib2.urlopen(req)
        result = response.read()
        response.close()
        soup = BS.BeautifulSoup(result)
        links = soup.findAll("table")[1].findAll("a")

        # Select a subset (or all)
        if numLinks is not None:
            totalLinks = links[startLink:(startLink + numLinks)]
        else:
            totalLinks = links[startLink:]

        c = self.db.cursor()
        currentLink = startLink
        for link in totalLinks:
            print "Working on link %d" % currentLink
            name = link.text
            nameHash = sha1.sha(name).hexdigest()
            nameLink = link["href"][2:]

            result = self.parseNamePage(self.BASE + nameLink)
            if (result is not None):
                c.execute('insert into names (name, hash, link, comments) values (?,?,?,?)', (unescape(name), nameHash, nameLink, result["comments"]))
                self.db.commit()
    
                for film in result["allFilms"]:
                    c.execute("insert into Films(hash, title, link, originalLink, comments) values (?, ?, ?, ?, ?)",(nameHash, film["filmName"], film["link"], film["originalLink"], film["comments"]))
            
            # Sleep for a bit to cutdown on usage
            sleepTime = random.randrange(5, 10)
            print "Sleeping for %d" % sleepTime
            time.sleep(sleepTime)
            currentLink += 1

        self.db.commit()
        c.close()

    def doRequest(self, href):
        req = urllib2.Request(href)
        try:
            response = urllib2.urlopen(req)
            result = response.read()
            response.close()
            return result
        except urllib2.HTTPError:
            return None


    def parseNamePage(self, href):
        # Open up new requests to load film links
        nameData = self.doRequest(href)

        if nameData is None:
            return None
        nameSoup = BS.BeautifulSoup(nameData)

        print "Working on %s" % (href)
        # Check if the video is simply on this page
        if nameSoup.findAll("script") != []:
            for script in nameSoup.findAll("script"):
                if self.swfRE.findall(script.text) != []:
                    filmResults = self.parseFilmPage(href)
                    
                    if filmResults is not None:
                        return {"comments": "",
                            "allFilms": [filmResults]}
                    else:
                        return None
        
        comments = ""
        for f in nameSoup.findAll("table")[1].findAll("td", attrs = {"class": "default"})[1].findAll("font")[0]:
            if isinstance(f, BS.NavigableString):
                if len(f) > self.JUNK_THRESHOLD:
                    comments += f

        potentialFilmLinks = nameSoup.findAll("table")[1].findAll("td", attrs = {"class": "default"})[1].findAll("font")[0].findAll("img")
        allFilms = []
        for potentialFilmLink in potentialFilmLinks:
            a = potentialFilmLink.findNext()
            filmName = a.text
            try:
                potentialFilmHref = a["href"]
            except KeyError:
                continue
            print "Working on %s" % (self.BASE + potentialFilmHref)
            filmResults = self.parseFilmPage(self.BASE + potentialFilmHref)
            if filmResults is not None:
                filmResults["filmName"] = unescape(filmName)
                allFilms.append(filmResults)

        return {"comments": unescape(comments).strip(),
                "allFilms": allFilms}

    def parseFilmPage(self, href):
        filmData = self.doRequest(href)

        if filmData is None:
            return None
        filmSoup = BS.BeautifulSoup(filmData)

        originalLink = ""
        link = ""
        filmName = ""
        for s in filmSoup.findAll("script"):
            r = self.fileRE.findall(s.text)
            
            if r != []:
                # Okay, got link to flv
                link = r[0]

                # Now check for link to original file
                for t in s.nextSiblingGenerator():
                    if isinstance(t, BS.Tag):
                        if t.get("href"):
                            filmName = unescape(t.text)
                            originalLink = t.get("href")
        
        # If we get to this point and link is still "",
        # then something is up and we should just return
        if (link == ""):
            return None

        comments = ""
        if (len(filmSoup.findAll("table")) == 2):
            tableIndex = 1
            tdIndex = 1
        else:
            tableIndex = 2
            tdIndex = 0

        for f in filmSoup.findAll("table")[tableIndex].findAll("td", attrs = {"class": "default"})[tdIndex]:
            if isinstance(f, BS.NavigableString):
                if len(f) > self.JUNK_THRESHOLD:
                    if (f.find("INSERT DESCRIPTION") != -1):
                        continue
                    elif (f.find("END DESCRIPTION PARAGRAPHS") != -1):
                        continue
                    elif (f.find("TOUCH FROM HERE") != -1):
                        continue
                    else:
                        comments += f

        return {"link": link,
                "filmName": filmName,
                "originalLink": originalLink,
                "comments": unescape(comments).strip()}

    def updateUbuWebDBOld(self):
        # Open Ubuweb film page
        req = urllib2.Request("http://www.ubu.com/film/")
        response = urllib2.urlopen(req)
        result = response.read()
        response.close()
        soup = BS.BeautifulSoup(result)
        links = soup.findAll("table")[1].findAll("a")
    
        fewerLinks = links[1:5]
        c = self.db.cursor()
        for link in fewerLinks:
            name = link.text
            nameHash = sha1.sha(name).hexdigest()
            href = link["href"][2:]
            c.execute('insert into names (name, hash, link) values (?,?,?)', (unescape(name), nameHash, href))
            self.db.commit()

            # Open up new requests to load film links
            req = urllib2.Request(self.BASE + href)
            response = urllib2.urlopen(req)
            result = response.read()
            response.close()
            nameSoup = BS.BeautifulSoup(result)
            print "Working on %s" % (self.BASE + href)
            potentialFilmLinks = nameSoup.findAll("table")[1].findAll("font")[2].findAll("img")
            for potentialFilmLink in potentialFilmLinks:
                a = potentialFilmLink.findNext()
                name = a.text
                potentialHref = a["href"]
                print "Working on %s" % (self.BASE + potentialHref)
                filmRequest = urllib2.Request(self.BASE + potentialHref)
                try:
                    filmResponse = urllib2.urlopen(filmRequest)
                except urllib2.HTTPError:
                    continue
                filmResult = filmResponse.read()
                filmResponse.close()
                filmSoup = BS.BeautifulSoup(filmResult)

                for s in filmSoup.findAll("script"):
                    r = self.fileRE.findall(s.text)

                    if r != []:
                        c.execute("insert into films (hash, title, link) values (?,?,?)", (nameHash, unescape(name), r[0]))

                #filmLink = self.fileRE.findall(filmSoup.findAll("script")[2].text)[0]        
                self.db.commit()
            #addDirectoryItem(name=link.text, isFolder = False)

    def getAllData(self):
        names = {}
        c = self.db.cursor()
        for row in c.execute("select * from names"):
            name = row[1]
            nameHash = row[2]
            names[nameHash] = {}
            names[nameHash]['nid'] = row[0]
            names[nameHash]['name'] = name
            names[nameHash]['links'] = []
        c.close()
        
        c = self.db.cursor()
        for nameHash in names.keys():
            for film in c.execute("select * from Films where hash=?", (nameHash,)):
                names[nameHash]['links'].append((film[2], film[3]))

        c.close()
        return names

    def getNames(self):
        names = []
        c = self.db.cursor()
        for row in c.execute("select * from Names"):
            name = {}
            name["nid"] = row[0]
            name["name"] = row[1]
            name["nameHash"] = row[2]
            name["link"] = row[3]
            name["comments"] = row[4]

            names.append(name)
        c.close()
        return names

    def getFilmsByNameHash(self, nameHash):
        films = []
        c = self.db.cursor()
        for film in c.execute("select * from Films where hash=?", (nameHash,)):
            films.append([film[2], film[3]])
        c.close()
        return films

    def getLastUpdated(self):
        c = self.db.cursor()
        c.execute("select lastUpdated from Status")
        result = c.fetchone()
        
        lastUpdated = float(result[0])
        c.close()

        return lastUpdated

    def makeFilmDict(self, filmRow):
        film = {}
        film["fid"] = filmRow[0]
        film["nameHash"] = filmRow[1]
        film["filmTitle"] = filmRow[2]
        film["filmLink"] = filmRow[3]
        film["originalLink"] = filmRow[4]
        film["comments"] = filmRow[5]

        return film

    def getFilmsByNameID(self, nameID):
        films = []
        c = self.db.cursor()

        c.execute("select * from Names where nid=?", (nameID,))
        name = c.fetchone()
        c.close()

        c = self.db.cursor()
        nameHash = name[2]
        for film in c.execute("select * from Films where hash=?", (nameHash,)):
            films.append(self.makeFilmDict(film))
        c.close()
        return films


if __name__ == "__main__":
    u = UbuWebFilm()
    print u.getAllData()
    print u.getNames()
    print u.getFilmsByNameHash("fe57c250f11382828b449672186a70abfc88ffb1")
    print u.getFilmsByNameID(1)
