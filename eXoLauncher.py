# coding=UTF-8
import zipfile
from zipfile import BadZipfile
import re
import os.path
import os
import binascii
import sys
import getopt
import shutil
import time
import ConfigParser
import subprocess
import logging
import datetime
import random
import string
import uuid
import traceback
import xml.etree.ElementTree as ET

#*****************************************************************
#*****************************************************************
# Tools
#*****************************************************************
#*****************************************************************
def timestamp():
   return datetime.datetime.now().strftime('%Y%m%d%H%M%S.%f')
   
def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))

tempDirs = []
def mkTempDir():
	tempDir = os.path.join(workingdir, id_generator())
	os.makedirs(tempDir)
	tempDirs.append(tempDir)
	return(tempDir)

def rmTempDir(tempDir):
	if tempDir in tempDirs:
		retry = 0
		while True:
			try:
				shutil.rmtree(tempDir)
				tempDirs.remove(tempDir)
				return
			except:
				#Sometimes rmtree fails so we will retry 3 times
				if retry >= 2:
					raise
			retry = retry + 1
			time.sleep(1)

def getCRC(filename):
 filedata = open(filename, 'rb').read()
 return binascii.crc32(filedata)

def zipdir(path, ziph):
	# ziph is zipfile handle
	for root, dirs, files in os.walk(path):
		for file in files:
			absfilepath = os.path.join(root, file)
			relfilepath = os.path.relpath(absfilepath, path)
			logging.debug("Archiving file : " + relfilepath)
			ziph.write(absfilepath, relfilepath)

def searchFileInDirectories(dirs = [], filename = ""):
	# For each directory
	for dir in dirs:
		if os.path.isdir(dir):
			path = os.path.join(dir, filename)
			if os.path.isfile(path):
				return path

def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
#*****************************************************************
# Constants
_Name				= "eXoLauncher"
_Version			= 0.2
_eXoLauncherHelp 	= "Usage : eXoLauncher.py -r <eXo file>"

# Mode
_NoMode				= 0
_LaunchMode			= 1
_ImportMode			= 2
_ImportLBMode		= 3

# eXo files
_GameIni			= "game.ini"
_DBConf				= "dosbox.conf"
_DescTxt			= "desc.txt"

# ini files
_eXoLoaderSection	= "Main"
_CollectionKey		= "Collection"
_GameNameKey		= "GameName"
_ArchiveKey			= "Archive"
_DBConfKey			= "DBConf"

# Output directories
_GamesDir 		= "games"
_FrontsDir 		= "fronts"
_BacksDir 		= "backs"
_TitlesDir 		= "titles"
_ScreensDir 	= "screenshots"
_ManualsDir 	= "manuals"

# eXo collection stuffs
_eXoDosKey = "!dos"

# Meagre stuffs
_Meagre			= "Meagre"

#*****************************************************************
# Globals
asciiCorrector			= re.compile(r'[^\x00-\x7F]+')
nameCleaner				= re.compile(r"\(.*\)")
scriptpath 				= os.path.realpath(__file__)
scriptdir				= os.path.dirname(scriptpath)
scriptName, scriptExt 	= os.path.splitext(os.path.basename(scriptpath))
logfile 				= scriptName + ".log"
cfgfile 				= scriptName + ".ini"
dbbaseconf				= os.path.join(scriptdir, _DBConf)
workingdir 				= os.path.join(scriptdir, "_temp")
savesdir 				= os.path.join(scriptdir, "saves")

# Init working directories
if not os.path.isdir(workingdir): 		os.makedirs(workingdir)
if not os.path.isdir(savesdir): 		os.makedirs(savesdir)

#*****************************************************************
# Logging
root = logging.getLogger()
root.setLevel(logging.DEBUG)

# Adding file log handleer
with open(logfile, 'w'): pass
fileHandler = logging.FileHandler(logfile)
fileHandler.setLevel(logging.DEBUG)
fileHandler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
root.addHandler(fileHandler)

# Adding stdout log handler
stdoutHandler = logging.StreamHandler(sys.stdout)
stdoutHandler.setLevel(logging.INFO)
stdoutHandler.setFormatter(logging.Formatter('%(message)s'))
root.addHandler(stdoutHandler)

#*****************************************************************
# Configuration
# Verify config file
if not os.path.isfile(cfgfile):
	logging.error("No eXoLauncher configuration file ('" + cfgfile + "') found!")
	sys.exit(1)

# Verify dosbox base conf
if not os.path.isfile(dbbaseconf):
	logging.error("No base dosbox.conf ('" + dbbaseconf + "') found!")
	sys.exit(1)

# Read config file
logging.debug("<<< Global configuration >>>")
logging.debug("Reading configuration file...")
eXoLConfig = ConfigParser.ConfigParser()
eXoLConfig.optionxform=str # For case sensitiveness

# Open config file
eXoLConfig.read(cfgfile)

# Get DosBOX path
dosboxpath = eXoLConfig.get(_eXoLoaderSection, "DosBOX")
logging.debug("DosBOX : " + dosboxpath)
if not os.path.isfile(dosboxpath):
	logging.error("DosBOX '" + dosboxpath + "' not found!")
	sys.exit(1)

# Get eXoDOS collections
eXoCollections = []
for option in eXoLConfig.options("Collections"):
	colpath = eXoLConfig.get("Collections", option)
	logging.debug("Collection[" + option + "] : " + colpath)
	eXoCollections.append(colpath)

#*****************************************************************
#*****************************************************************
# Launch Mode
#*****************************************************************
#*****************************************************************
def eXoLaunch(romfile):
	if not os.path.isfile(romfile):
		logging.error("Invalid \"rom\" file ('" + romfile + "')!")
		logging.info(_eXoLauncherHelp)
		sys.exit(1)
	
	# Opening rom
	try:
		eXoFile = zipfile.ZipFile(romfile)
		eXoFile.getinfo(_GameIni)
		eXoFile.getinfo(_DBConf)
	except (BadZipfile, KeyError):
		logging.error("File '" + romfile + "' does not seems to be a valid eXo file!")
		sys.exit(1)

	# Reading config
	logging.info("Reading eXo file '" + romfile + "'...")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.readfp(eXoFile.open(_GameIni))
	gamename	= configparser.get(_eXoLoaderSection, _GameNameKey)
	archive		= configparser.get(_eXoLoaderSection, _ArchiveKey)

	if not gamename:
		logging.error("Invalid Game Name. Contact your guru!")
		sys.exit(1)

	if not archive:
		logging.error("Invalid Archive. Contact your guru!")
		sys.exit(1)

	logging.info("GameName : " + gamename)
	logging.info("Archive  : " + archive)

	# Verify archive
	archivepath = searchFileInDirectories(eXoCollections, archive)
	if not archivepath:
		logging.error("No archive '" + archivepath + "' found in any collection!")
		sys.exit(1)

	#*****************************************************************
	# Pre-processing
	logging.debug("<<< Pre-processing >>>")

	# Setting up directories
	gamedir 	= mkTempDir()
	savepath 	= os.path.join(savesdir, gamename + ".zip")
	gamedbconf	= os.path.join(gamedir, _DBConf)

	# Logging
	logging.debug("Game directory : '" + gamedir + "'")
	logging.debug("Savegame : '" + savepath + "'")
	logging.debug("Dosbox config file : '" + gamedbconf + "'")
	
	# Extracting game
	logging.info("Extracting game archive...")
	zipFilesCRC = dict()
	zfile = zipfile.ZipFile(archivepath)
	for info in zfile.infolist():
		logging.debug("Extracting '" + info.filename + "'")
		zipFilesCRC[info.filename] = info.CRC
		zfile.extract(info, gamedir)
	zfile.close()

	# if there is a save
	logging.info("Looking for a save archive...")
	if os.path.isfile(savepath):
		logging.info("> Extracting save archive...")
		# Extract it
		savezip = zipfile.ZipFile(savepath)
		savezip.extractall(gamedir)
		savezip.close()
	else:
		logging.info("> No savegame found")

	# Converting/Modifying the configuration
	logging.info("Configuration...")
	confout	= open(gamedbconf, "wb")
	for line in eXoFile.open(_DBConf):
		newline = line
		newline = newline.replace(r"__DB_ROOT_DIR__", gamedir)
		confout.write(newline)
	confout.close()

	#*****************************************************************
	# Execution
	logging.debug("<<< Execution >>>")

	# Launching dosbox
	logging.info("Launching DOSBox...")
	process = subprocess.Popen([dosboxpath, r'-noconsole', r'-exit', r'-conf', dbbaseconf, r'-conf', gamedbconf])
	process.wait()
	logging.info("DOSBox exited(" + str(process.returncode) + ")")

	#*****************************************************************
	# Post-processing
	logging.debug("<<< Post-processing >>>")

	# Deleting configuration
	os.remove(gamedbconf)

	# Remove unmodified stuffs
	logging.info("Cleaning game directory...")
	for zipFile in reversed(sorted(zipFilesCRC.keys())):
		localFile 	= os.path.join(gamedir,zipFile)
		if os.path.isfile(localFile):
			zipFileCRC		= zipFilesCRC[zipFile]
			localFileCRC 	= getCRC(localFile) % 2**32
			#logging.info(localFile + "[" + str(localFileCRC) + "]")
			if localFileCRC == zipFileCRC:
				logging.debug("Removing unmodified file '" + localFile + "'")
				os.remove(localFile)
		elif os.path.isdir(localFile):
			if not os.listdir(localFile):
				logging.debug("Removing unmodified dir '" + localFile + "'")
				os.rmdir(localFile)

	# If there is stuff left
	logging.info("Saving...")
	if os.listdir(gamedir):
		# Save it
		logging.info("> Saving modified files into '" + savepath + "'...")
		zipf = zipfile.ZipFile(savepath, 'w')
		zipdir(gamedir, zipf)
		zipf.close()
	else:
		logging.info("> No modified files.")

	# Removing game directory
	logging.info("Removing temporary directory...")
	rmTempDir(gamedir)

#*****************************************************************
#*****************************************************************
# Convert Mode
#*****************************************************************
#*****************************************************************
def eXoCopyFile(eXoGameName, eXoFilePath, outputDir):
	if eXoFilePath and outputDir:
		if os.path.isfile(eXoFilePath):
			logging.debug("Import file '" + eXoFilePath + "' into '" + outputDir + "...")
			filename, fileext 	= os.path.splitext(eXoFilePath)
			dstname				= eXoGameName + fileext
			dst					= os.path.join(outputDir, dstname)
			shutil.copyfile(eXoFilePath, dst)
			return(dst)

def eXoMoveFile(eXoGameName, eXoFilePath, outputDir):
	if eXoFilePath and outputDir:
		if os.path.isfile(eXoFilePath):
			logging.debug("Import file '" + eXoFilePath + "' into '" + outputDir + "...")
			filename, fileext 	= os.path.splitext(eXoFilePath)
			dstname				= eXoGameName + fileext
			dst					= os.path.join(outputDir, dstname)
			shutil.move(eXoFilePath, dst)
			return(dst)

def eXoCreateIniFile(eXoGameInfos, iniOutPath):
	logging.debug("Creating ini file '" + iniOutPath + "'")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.add_section(_eXoLoaderSection)
	configparser.set(_eXoLoaderSection, _GameNameKey, eXoGameInfos.gamename)
	configparser.set(_eXoLoaderSection, _ArchiveKey, eXoGameInfos.archivename)
	with open(iniOutPath, 'w') as configfile: configparser.write(configfile)

def eXoConvertDosBOXConf(dbConfInPath, dbConfOutPath):
	# Converting/Modifying the configuration
	logging.debug("Converting DosBOX configuration '" + dbConfInPath + "' into '" + dbConfOutPath + "'")
	currentKey	= ""
	confin 		= open(dbConfInPath, "rb")
	confout		= open(dbConfOutPath, "wb")
	for line in confin:
		#if line is a key
		if "[" in line:
			# Memorize it
			currentKey = line.strip()
		
		# Don't import dosbox base items (They are in the base eXoLauncher dosbox.conf)
		if currentKey not in ["[sdl]", "[render]", "[mixer]", "[midi]"]:
			newline = line
			# Replace eXo dependent stuffs
			newline = newline.replace(r".\games", r"__DB_ROOT_DIR__")
			confout.write(newline)
	confout.close()
	confin.close()

def eXoCreateFile(eXoGameInfos, dir):
	logging.debug("Creating eXoFile...")
	
	# init
	eXoFile = os.path.join(dir, eXoGameInfos.gamename + ".exo")

	# Create eXo file
	tempDir = mkTempDir()
	eXoCreateIniFile(eXoGameInfos, os.path.join(tempDir, _GameIni))
	eXoConvertDosBOXConf(eXoGameInfos.dbconf, os.path.join(tempDir, _DBConf))
	zipf = zipfile.ZipFile(eXoFile, 'w')
	zipdir(tempDir, zipf)
	zipf.close()
	rmTempDir(tempDir)
	
	return(eXoFile)

def eXoGetDesc(eXoDescFile):
	if eXoDescFile:
		if os.path.isfile(eXoDescFile):
			with open(eXoDescFile, "r") as myfile:
				return(myfile.read())

def eXoGetRealFilePath(dir, file):
	if file:
		return(os.path.join(dir, file))

class GameInfos:
	def __init__(self, 
	eXoGameDir,
	eXoIniPath):
		configparser = ConfigParser.ConfigParser()
		configparser.optionxform=str # For case sensitiveness
		configparser.read(os.path.join(eXoGameDir, _Meagre, "IniFile", eXoIniPath))
		self.gamename 		= os.path.splitext(os.path.basename(eXoIniPath))[0]
		self.archivename 	= self.gamename + ".zip"
		self.exofile		= None
		self.dbconf			= os.path.join(eXoGameDir, _DBConf)
		self.name			= asciiCorrector.sub(' ', configparser.get("Main", "Name"))
		self.genre			= asciiCorrector.sub(' ', configparser.get("Main", "Genre"))
		self.publisher		= asciiCorrector.sub(' ', configparser.get("Main", "Publisher"))
		self.developer		= asciiCorrector.sub(' ', configparser.get("Main", "Developer")) 
		self.year			= asciiCorrector.sub(' ', configparser.get("Main", "Year"))
		self.serie			= asciiCorrector.sub(' ', configparser.get("Main", "Series"))
		self.info			= asciiCorrector.sub(' ', eXoGetDesc(eXoGetRealFilePath(os.path.join(eXoGameDir, _Meagre, "About"), 	configparser.get("Main", "About"))))
		self.front 			= eXoGetRealFilePath(os.path.join(eXoGameDir, _Meagre, "Front"), 	configparser.get("Main", "Front01"))
		self.back 			= eXoGetRealFilePath(os.path.join(eXoGameDir, _Meagre, "Back"), 	configparser.get("Main", "Back01"))
		self.title 			= eXoGetRealFilePath(os.path.join(eXoGameDir, _Meagre, "Title"), 	configparser.get("Main", "Title01"))
		self.screen 		= eXoGetRealFilePath(os.path.join(eXoGameDir, _Meagre, "Screen"), 	configparser.get("Main", "Screen01"))
		self.manual 		= eXoGetRealFilePath(os.path.join(eXoGameDir, _Meagre, "Manual"), 	configparser.get("Main", "Manual"))

	def update(self, 
	exofile,
	front,
	back,
	title,
	screen,
	manual):
		self.exofile		= exofile
		self.front 			= front
		self.back 			= back
		self.title 			= title
		self.screen 		= screen
		self.manual 		= manual

def eXoImportGame(eXoGameInfos, outputDirs):
	logging.info("Importing game '" + eXoGameInfos.gamename + "'...")
	
	# Verifying DosBOX conf
	if not os.path.isfile(eXoGameInfos.dbconf):
		logging.warning("DosBOX config file '" + eXoGameInfos.dbconf + "' not found for " + eXoGameInfos.gamename + "! -> Skipping")
		return

	# Verifying archive
	if not searchFileInDirectories(eXoCollections, eXoGameInfos.archivename):
		logging.warning("No archive '" + eXoGameInfos.archivename + "' found in any collection! -> Skipping")
		return
	
	# Create eXoFile
	eXoGameInfos.update(
	eXoCreateFile(eXoGameInfos, outputDirs[_GamesDir]),
	eXoCopyFile(eXoGameInfos.gamename, eXoGameInfos.front, outputDirs[_FrontsDir]),
	eXoCopyFile(eXoGameInfos.gamename, eXoGameInfos.back, outputDirs[_BacksDir]),
	eXoCopyFile(eXoGameInfos.gamename, eXoGameInfos.title, outputDirs[_TitlesDir]),
	eXoCopyFile(eXoGameInfos.gamename, eXoGameInfos.screen, outputDirs[_ScreensDir]),
	eXoCopyFile(eXoGameInfos.gamename, eXoGameInfos.manual, outputDirs[_ManualsDir]))
	return(eXoGameInfos)

def findIni(dir):
	for root, dirs, files in os.walk(dir):
		for file in files:
			if ".ini" in file:
				return(os.path.basename(file))

def eXoConvertDir(dir, outputDirs):
	# Verify
	if not os.path.isdir(dir):
		logging.error("Directory '" + dir + "' not found!")
		return(1)
	
	logging.info("Converting '" + dir +"' directory...")
	eXoDir = os.path.join(dir, _eXoDosKey)
	
	if not os.path.isdir(eXoDir):
		logging.error("Directory '" + dir + "' does not seems to be an eXoDOS directory (no '!dos' dir inside)!")
		return(1)
	
	# Process subirectories
	eXoGamesInfos = []
	for item in os.listdir(eXoDir):
		eXoGameDir = os.path.join(eXoDir,item)
		if os.path.isdir(eXoGameDir):
			eXoIni = findIni(eXoGameDir)
			if eXoIni:
				eXoGamesInfos.append(eXoImportGame(GameInfos(eXoGameDir, eXoIni), outputDirs))
	
	return(eXoGamesInfos)

def eXoConvertArchive(eXoGamesArcPath, outputDirs):
	# If archive not exists
	if not os.path.isfile(eXoGamesArcPath):
		logging.error("File '" + eXoGamesArcPath + "' not found!")
		return(1)
	
	logging.debug("Converting archive file '" + eXoGamesArcPath + "'...")
	
	# Open archive
	logging.info("Opening archive file '" + eXoGamesArcPath + "'...")
	try:
		archive = zipfile.ZipFile(eXoGamesArcPath)
		archive.getinfo(_eXoDosKey + "/")
	except KeyError:
		logging.error("File '" + eXoGamesArcPath + "' does not seems to be an eXoDOS archive (no '!dos' dir inside)!")
		return(1)
	except BadZipfile:
		logging.error("File '" + eXoGamesArcPath + "' is not a valid zip archive!")
		return(1)

	# Creating temp dir
	logging.info("Creating temporary directory...")
	tempDir = mkTempDir()

	# Convert
	logging.info("Extracting archive file '" + eXoGamesArcPath + "'...")
	archive.extractall(tempDir)
	
	# Convert directory
	eXoGamesInfos = eXoConvertDir(tempDir, outputDirs)
	
	# Removing temp directory
	logging.info("Removing temporary directory...")
	rmTempDir(tempDir)
	
	return(eXoGamesInfos)

def eXoConvertCollection(collection, outputDirs, doImportArtworks, doImportManuals):
	# According to parameter (file/directory)
	if os.path.isfile(collection):
		# Convert archive
		return(eXoConvertArchive(collection, outputDirs))
	elif os.path.isdir(collection):
		# Convert directory
		return(eXoConvertDir(collection, outputDirs))
	else:
		logging.error("File '" + collection + "' not found!")
		return(1)

def eXoImportCollection(collection, outputDir, doImportArtworks, doImportManuals):
	# Game dir
	outputDirs = dict()
	outputDirs[_GamesDir] 	= os.path.join(outputDir, _GamesDir)
	outputDirs[_FrontsDir] 	= None
	outputDirs[_BacksDir] 	= None
	outputDirs[_TitlesDir] 	= None
	outputDirs[_ScreensDir] = None
	outputDirs[_ManualsDir] = None
	
	# Artwork
	if doImportArtworks:
		outputDirs[_FrontsDir] 	= os.path.join(outputDir, _FrontsDir)
		outputDirs[_BacksDir] 	= os.path.join(outputDir, _BacksDir)
		outputDirs[_TitlesDir] 	= os.path.join(outputDir, _TitlesDir)
		outputDirs[_ScreensDir] = os.path.join(outputDir, _ScreensDir)
	
	# Manuals
	if doImportManuals:
		outputDirs[_ManualsDir] = os.path.join(outputDir, _ManualsDir)
	
	# Create output dirs
	for dir in outputDirs.values():
		if dir and not os.path.isdir(dir): 
			os.makedirs(dir)

	# Convert collection
	return(eXoConvertCollection(collection, outputDirs, doImportArtworks, doImportManuals))

def findElement(parent, elementName, key, value):
	for element in parent.findall(elementName):
		if element.find(key).text == value:
			return element

def eXoImportCollectionLB(collection, lbDir, doImportArtworks, doImportManuals):
	logging.info("Exporting collections to LaunchBox...")
	
	lbXml 			= os.path.join(lbDir, "LaunchBox.xml")
	lbGamesDir		= os.path.join(lbDir, "Games")
	lbImagesDir		= os.path.join(lbDir, "Images")
	lbManualsDir	= os.path.join(lbDir, "Manuals")
	lbPlatform		= "MS-DOS"
	lbEmulator		= "eXoLauncher"
	
	if not os.path.isfile(lbXml):
		logging.error("File '%r' not found!", lbXml)
		return(1)
	
	if not os.path.isdir(lbGamesDir):
		logging.error("Directory '%r' not found!", lbGamesDir)
		return(1)
		
	if not os.path.isdir(lbImagesDir):
		logging.error("Directory '%r' not found!", lbImagesDir)
		return(1)
		
	if not os.path.isdir(lbManualsDir):
		logging.error("Directory '%r' not found!", lbManualsDir)
		return(1)
	
	logging.info("Parsing 'LaunchBox.xml'...")
	xmlDoc 	= ET.parse(lbXml)
	lbElm 	= xmlDoc.getroot()
	
	# Caching games/platforms
	logging.info("Caching all games...")
	lbGames = dict()
	for gameElement in lbElm.findall("Game"):
		lbGameName 		= gameElement.find("Title").text
		lbGamePlateform = gameElement.find("Platform").text
		if lbGameName not in lbGames: lbGames[lbGameName] = dict()
		lbGames[lbGameName][lbGamePlateform] = gameElement
	
	# Creating destination directories
	lbeXoGamesDir 	= os.path.join(lbGamesDir, lbPlatform)
	lbeXoImagesDir	= os.path.join(lbImagesDir, lbPlatform)
	lbeXoManualsDir	= os.path.join(lbManualsDir, lbPlatform)
	lbeXoFrontsDir	= os.path.join(lbeXoImagesDir, "Front")
	lbeXoBacksDir	= os.path.join(lbeXoImagesDir, "Back")
	lbeXoScreensDir	= os.path.join(lbeXoImagesDir, "Screenshot")
	if not os.path.isdir(lbeXoGamesDir): os.makedirs(lbeXoGamesDir)
	if not os.path.isdir(lbeXoImagesDir): os.makedirs(lbeXoImagesDir)
	if not os.path.isdir(lbeXoManualsDir): os.makedirs(lbeXoManualsDir)
	if not os.path.isdir(lbeXoFrontsDir): os.makedirs(lbeXoFrontsDir)
	if not os.path.isdir(lbeXoBacksDir): os.makedirs(lbeXoBacksDir)
	if not os.path.isdir(lbeXoScreensDir): os.makedirs(lbeXoScreensDir)
	
	# Creating temp dir
	logging.info("Creating temporary directory...")
	tempDir = mkTempDir()
	
	# Import in temporary directory
	eXoGamesInfos = eXoImportCollection(collection, tempDir, doImportArtworks, doImportManuals)

	# Emulator
	isEmulatorCreated = False
	emuId	= str(uuid.uuid1())
	emuElm 	= findElement(lbElm, "Emulator", "Title", lbEmulator)
	if emuElm is not None:
		logging.info("Reading Emulator '%s' informations...", lbEmulator)
		isEmulatorCreated = False
		emuId = emuElm.find("ID").text
	else:
		logging.info("Creating Emulator '%s'...", lbEmulator)
		isEmulatorCreated = True
		emuElm = ET.SubElement(lbElm, "Emulator")
		ET.SubElement(emuElm, "ID").text 								= emuId
		ET.SubElement(emuElm, "Title").text 							= lbEmulator
		ET.SubElement(emuElm, "ApplicationPath").text 					= scriptpath
		ET.SubElement(emuElm, "CommandLine").text 						= "-r"
		ET.SubElement(emuElm, "NoQuotes").text 							= "false"
		ET.SubElement(emuElm, "NoSpace").text 							= "false"
		ET.SubElement(emuElm, "HideConsole").text 						= "false"
		ET.SubElement(emuElm, "FileNameWithoutExtensionAndPath").text 	= "false"
		ET.SubElement(emuElm, "DefaultPlatform")
	
	# Platform
	isPlatformCreated = False
	platformElm = findElement(lbElm, "Platform", "Name", lbPlatform)
	if platformElm is None:
		logging.info("Creating Platform '%s'...", lbPlatform)
		isPlatformCreated = True
		platformElm = ET.SubElement(lbElm, "Platform")
		ET.SubElement(platformElm, "Name").text = str(lbPlatform)
	
	# EmulatorPlatform
	if isEmulatorCreated or isPlatformCreated:
		logging.info("Creating EmulatorPlatform...")
		platformElm = ET.SubElement(lbElm, "EmulatorPlatform")
		ET.SubElement(platformElm, "Emulator").text = emuId
		ET.SubElement(platformElm, "Platform").text = lbPlatform
		ET.SubElement(platformElm, "Default").text = "false"
		ET.SubElement(platformElm, "CommandLine")

	for gameInfos in eXoGamesInfos:
		lbeXoGame = nameCleaner.sub('', gameInfos.gamename).strip()
		logging.info("Searching game '%s'...", lbeXoGame)
		if lbeXoGame in lbGames:
			if lbPlatform in lbGames[lbeXoGame]:
				logging.info("> Game '%s' found for Platform '%s'! Removing...", lbeXoGame, lbPlatform)
				lbElm.remove(lbGames[lbeXoGame][lbPlatform])
				del lbGames[lbeXoGame][lbPlatform]
		logging.info("Importing game '%s'...", lbeXoGame)
		gameElm = ET.SubElement(lbElm, "Game")
		ET.SubElement(gameElm, "ID").text 				= str(uuid.uuid1())
		ET.SubElement(gameElm, "Title").text 			= lbeXoGame
		ET.SubElement(gameElm, "ApplicationPath").text 	= eXoMoveFile(gameInfos.gamename, gameInfos.exofile, lbeXoGamesDir)
		ET.SubElement(gameElm, "Developer").text 		= gameInfos.developer
		ET.SubElement(gameElm, "Publisher").text 		= gameInfos.publisher
		ET.SubElement(gameElm, "ReleaseDate").text 		= datetime.datetime(int(gameInfos.year), 1, 1, 0, 0).isoformat()
		ET.SubElement(gameElm, "Genre").text 			= gameInfos.genre
		ET.SubElement(gameElm, "Series").text 			= gameInfos.serie
		ET.SubElement(gameElm, "Notes").text 			= gameInfos.info
		ET.SubElement(gameElm, "DateAdded").text 		= datetime.datetime.now().isoformat()
		ET.SubElement(gameElm, "DateModified").text 	= datetime.datetime.now().isoformat()
		ET.SubElement(gameElm, "Platform").text 		= lbPlatform
		ET.SubElement(gameElm, "Emulator").text 		= emuId
		
		# Artworks and manual
		if gameInfos.front: 	eXoMoveFile(lbeXoGame, gameInfos.front, lbeXoFrontsDir)
		if gameInfos.back: 		eXoMoveFile(lbeXoGame, gameInfos.back, lbeXoBacksDir)
		if gameInfos.title: 	eXoMoveFile(lbeXoGame + "-01", gameInfos.title, lbeXoScreensDir)
		if gameInfos.screen:	eXoMoveFile(lbeXoGame + "-02", gameInfos.screen, lbeXoScreensDir)
		if gameInfos.manual: 	ET.SubElement(gameElm, "ManualPath").text = eXoMoveFile(lbeXoGame, gameInfos.manual, lbeXoManualsDir)
		
		# Caching game
		if lbeXoGame not in lbGames: lbGames[lbeXoGame] = dict()
		lbGames[lbeXoGame][lbPlatform] = gameElm

	# Save the xml
	logging.info("Backing up 'LaunchBox.xml'...")
	shutil.copyfile(lbXml, os.path.join(lbDir, "LaunchBox.eXoBackup." + timestamp() + ".xml"))
	logging.info("Saving updated 'LaunchBox.xml'...")
	indent(lbElm)
	gamelistTree = ET.ElementTree(lbElm)
	xmlDoc.write(os.path.join(lbDir, "LaunchBox.xml"), xml_declaration=True)

	# Removing temp directory
	logging.info("Removing temporary directory...")
	rmTempDir(tempDir)


#*****************************************************************
#*****************************************************************
# Main
#*****************************************************************
#*****************************************************************

def main(argv):
	#*****************************************************************
	# Arguments
	mode 				= _NoMode
	romfile				= ""
	collection			= ""
	outputDir			= ""
	doImportArtworks	= False
	doImportManuals		= False
	
	try:
	  opts, args = getopt.getopt(argv,"hamr:i:o:l:",["rom="])
	except getopt.GetoptError:
	  logging.info(_eXoLauncherHelp)
	  sys.exit(2)
	for opt, arg in opts:
	  if opt == '-h':
		logging.info(_eXoLauncherHelp)
		sys.exit()
	  elif opt in ("-r", "--rom"):
		mode = _LaunchMode
		romfile = arg
	  elif opt in ("-i", "--import"):
		mode = _ImportMode
		collection = arg
	  elif opt in ("-l", "--outputlb"):
		mode = _ImportLBMode
		collection = arg
	  elif opt in ("-o", "--output"):
		outputDir = arg
		if not os.path.isdir(outputDir):
			logging.error("Invalid output directory '" + outputDir + "'!")
			sys.exit(2)
	  elif opt in ("-a"):
		doImportArtworks = True
	  elif opt in ("-m"):
		doImportManuals = True

	if mode == _LaunchMode:
		# Launch the rom file
		eXoLaunch(romfile)
	elif mode == _ImportMode:
		if not outputDir:
			logging.error("You must provides an output directory (-o)!")
			sys.exit(2)
		# Convert the collection
		eXoImportCollection(collection, outputDir, doImportArtworks, doImportManuals)
	elif mode == _ImportLBMode:
		if not outputDir:
			logging.error("You must provides LaunchBox directory (-l)!")
			sys.exit(2)
		# Convert the collection
		eXoImportCollectionLB(collection, outputDir, doImportArtworks, doImportManuals)
	else:
		logging.info(_eXoLauncherHelp)
		sys.exit(2)

if __name__ == "__main__":
	try:
		main(sys.argv[1:])
	except:
		logging.error("****************************")
		logging.error("Unexpected error!")
		logging.info("Cleaning stuffs...")
		for tempDir in tempDirs:
			rmTempDir(tempDir)
		logging.error(traceback.format_exc())
