# coding=UTF-8
import zipfile
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

def timestamp():
   now = time.time()
   localtime = time.localtime(now)
   milliseconds = '%03d' % int((now - int(now)) * 1000)
   return time.strftime('%Y%m%d%H%M%S', localtime) + milliseconds

def getCRC(filename):
 filedata = open(filename, 'rb').read()
 return binascii.crc32(filedata)

def zipdir(path, ziph):
	# ziph is zipfile handle
	for root, dirs, files in os.walk(path):
		for file in files:
			absfilepath = os.path.join(root, file)
			relfilepath = os.path.relpath(absfilepath, path)
			logging.info("Archiving file : " + relfilepath)
			ziph.write(absfilepath, relfilepath)

#*****************************************************************
# Constants
_NoMode				= 0
_ImportMode			= 1
_ImportAllMode		= 2
_LaunchMode			= 3
_GameIni			= "game.ini"
_DBConf				= "dosbox.conf"
_DescTxt			= "desc.txt"
_eXoGameDir 		= "Games"
_eXoLoaderSection	= "Main"
_eXoLauncherHelp 	= "Usage : eXoLauncher.py -r <romfile>"
_CollectionKey		= "Collection"
_GameNameKey		= "GameName"
_ArchiveKey			= "Archive"
_DBConfKey			= "DBConf"

#*****************************************************************
# Globals
scriptpath 				= os.path.realpath(__file__)
scriptdir				= os.path.dirname(scriptpath)
scriptName, scriptExt 	= os.path.splitext(os.path.basename(scriptpath))
logfile 				= scriptName + ".log"
cfgfile 				= scriptName + ".ini"
dbbaseconf				= os.path.join(scriptdir, _DBConf)
workingdir 				= os.path.join(scriptdir, "_temp")
savesdir 				= os.path.join(scriptdir, "saves")
gamesdir				= os.path.join(scriptdir, "games")
imagedir				= os.path.join(scriptdir, "images")
imagefrontdir			= os.path.join(imagedir, "fronts")
imagebackdir			= os.path.join(imagedir, "backs")
imagetitlesdir			= os.path.join(imagedir, "titles")
imagescreensdir			= os.path.join(imagedir, "screenshots")
manualsdir				= os.path.join(scriptdir, "manuals")

# Init working directories
if not os.path.isdir(workingdir): 		os.makedirs(workingdir)
if not os.path.isdir(savesdir): 		os.makedirs(savesdir)
if not os.path.isdir(gamesdir): 		os.makedirs(gamesdir)
if not os.path.isdir(imagedir): 		os.makedirs(imagedir)
if not os.path.isdir(imagefrontdir): 	os.makedirs(imagefrontdir)
if not os.path.isdir(imagebackdir): 	os.makedirs(imagebackdir)
if not os.path.isdir(imagetitlesdir): 	os.makedirs(imagetitlesdir)
if not os.path.isdir(imagescreensdir): 	os.makedirs(imagescreensdir)
if not os.path.isdir(manualsdir): 		os.makedirs(manualsdir)

# Init logger
with open(logfile, 'w'): pass
logging.basicConfig(filename=logfile, level=logging.INFO)

# Verify config file
if not os.path.isfile(cfgfile):
	print("No eXoLauncher configuration file ('" + cfgfile + "') found!")
	sys.exit(1)

# Verify dosbox base conf
if not os.path.isfile(dbbaseconf):
	print("No base dosbox.conf ('" + dbbaseconf + "') found!")
	sys.exit(1)

#*****************************************************************
# Configuration
logging.info("<<< Configuration >>>")
# Read config file
eXoLConfig = ConfigParser.ConfigParser()
eXoLConfig.optionxform=str # For case sensitiveness

# Open config file
eXoLConfig.read(cfgfile)

# Get DosBOX path
dosboxpath = eXoLConfig.get(_eXoLoaderSection, "DosBOX")
logging.info("DosBOX : " + dosboxpath)
if not os.path.isfile(dosboxpath):
	print("DosBOX '" + dosboxpath + "' not found!")
	sys.exit(1)

# Get eXoDOS collections
eXoCollections = dict()
for option in eXoLConfig.options("Collections"):
	colpath = eXoLConfig.get("Collections", option)
	logging.info("Collection[" + option + "] : " + colpath)
	eXoCollections[option] = colpath
	
# Get eXoDOS archives
eXoArchives = dict()
for option in eXoLConfig.options("Archives"):
	arcpath = eXoLConfig.get("Archives", option)
	logging.info("Archive[" + option + "] : " + arcpath)
	eXoArchives[option] = arcpath

#*****************************************************************
#*****************************************************************
# Launch Mode
#*****************************************************************
#*****************************************************************
def eXoLaunch(romfile):
	if not os.path.isfile(romfile):
		print("Invalid \"rom\" file ('" + romfile + "')!")
		print(_eXoLauncherHelp)
		sys.exit(1)

	#*****************************************************************
	# Read "rom" file
	collection	= ""
	gamename	= ""
	archive		= ""
	
	# Opening rom
	eXoFile = zipfile.ZipFile(romfile)

	# Reading config
	print("Reading \"rom\" file '" + romfile + "'")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.readfp(eXoFile.open(_GameIni))
	collection	= configparser.get(_eXoLoaderSection, _CollectionKey)
	gamename	= configparser.get(_eXoLoaderSection, _GameNameKey)
	archive		= configparser.get(_eXoLoaderSection, _ArchiveKey)

	#Verifying
	if not collection:
		print("Invalid Collection. Check config file!")
		sys.exit(1)

	if not gamename:
		print("Invalid Game Name. Check config file!")
		sys.exit(1)

	if not archive:
		print("Invalid Archive. Check config file!")
		sys.exit(1)

	# Collection
	if collection not in eXoCollections:
		print("Invalid collection '" + collection + "'!")
		sys.exit(1)

	# Archive
	archivepath = os.path.join(os.path.join(eXoCollections[collection], _eXoGameDir), archive)
	if not os.path.isfile(archivepath):
		print("Archive '" + archivepath + "' not found!")
		sys.exit(1)

	#*****************************************************************
	# Initialisation

	# Setting up directories
	gamedir 	= os.path.join(workingdir, timestamp())
	savepath 	= os.path.join(savesdir, gamename + ".zip")
	gamedbconf	= os.path.join(gamedir, _DBConf)

	# Logging
	logging.info("<<< Initialisation >>>")
	logging.info("Launching : [" + collection + "]" + gamename)
	logging.info("Archive : " + archive)
	logging.info("Game directory : '" + gamedir + "'")
	logging.info("Savegame : '" + savepath + "'")
	logging.info("Dosbox config file : '" + gamedbconf + "'")

	#*****************************************************************
	# Pre-processing
	logging.info("<<< Pre-processing >>>")

	# Creating game directory
	os.makedirs(gamedir)

	# Extracting game
	logging.info(">>> Extraction")
	zipFilesCRC = dict()
	zfile = zipfile.ZipFile(archivepath)
	for info in zfile.infolist():
		logging.info("Extracting '" + info.filename + "'")
		zipFilesCRC[info.filename] = info.CRC
		zfile.extract(info, gamedir)
	zfile.close()

	# if there is a save
	logging.info(">>> Savegame")
	if os.path.isfile(savepath):
		logging.info("Extracting save...")
		# Extract it
		savezip = zipfile.ZipFile(savepath)
		savezip.extractall(gamedir)
		savezip.close()
	else:
		logging.info("No savegame found")

	# Importing/Modifying the configuration
	logging.info(">>> Configuration")
	confout	= open(gamedbconf, "wb")
	for line in eXoFile.open(_DBConf):
		newline = line
		newline = newline.replace(r"__DB_ROOT_DIR__", gamedir)
		confout.write(newline)
	confout.close()

	#*****************************************************************
	# Execution
	logging.info("<<< Execution >>>")

	# Launching dosbox
	logging.info("Launching DOSBox...")
	process = subprocess.Popen([dosboxpath, r'-noconsole', r'-exit', r'-conf', dbbaseconf, r'-conf', gamedbconf])
	process.wait()
	logging.info("DOSBox was closed(" + str(process.returncode) + ")")

	#*****************************************************************
	# Post-processing
	logging.info("<<< Post-processing >>>")

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
				logging.info("Removing unmodified file '" + localFile + "'")
				os.remove(localFile)
		elif os.path.isdir(localFile):
			if not os.listdir(localFile):
				logging.info("Removing unmodified dir '" + localFile + "'")
				os.rmdir(localFile)

	# If there is stuff left
	logging.info("Saving...")
	if os.listdir(gamedir):
		# Save it
		logging.info("Saving modified files into '" + savepath + "'...")
		zipf = zipfile.ZipFile(savepath, 'w')
		zipdir(gamedir, zipf)
		zipf.close()
	else:
		logging.info("No modified files...")

	# Removing game directory
	logging.info("Removing game directory...")
	shutil.rmtree(gamedir)

#*****************************************************************
#*****************************************************************
# Import Mode
#*****************************************************************
#*****************************************************************
def importRenameFile(src, name, dstDir):
	filename, fileext 	= os.path.splitext(src)
	dstname				= name + fileext
	dst					= os.path.join(dstDir, dstname)
	shutil.copyfile(src, dst)
	

def eXoImportArts(eXoGamedir, eXoIniPath, eXoGameName):
	logging.info(">>> Importing artworks '" + eXoGameName + "'...")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.read(eXoIniPath)
	
	# Read values
	front 		= configparser.get("Main", "Front01")
	back		= configparser.get("Main", "Back01")
	title		= configparser.get("Main", "Title01")
	screenshot	= configparser.get("Main", "Screen01")
	manual		= configparser.get("Main", "Manual")
	
	# If valid
	if front:
		filename = os.path.join(eXoGamedir, "Meagre", "Front", front)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, imagefrontdir)
	if back:
		filename = os.path.join(eXoGamedir, "Meagre", "Back", back)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, imagebackdir)
	if title:
		filename = os.path.join(eXoGamedir, "Meagre", "Title", title)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, imagetitlesdir)
	if screenshot:
		filename = os.path.join(eXoGamedir, "Meagre", "Screen", screenshot)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, imagescreensdir)
	if manual:
		filename = os.path.join(eXoGamedir, "Meagre", "Manual", manual)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, manualsdir)

def eXoImportIniFile(collection, eXoGameName, archive, iniInPath, iniOutPath):
	logging.info(">>> Importing ini file '" + iniInPath + "' into '" + iniOutPath + "'")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.read(iniInPath)
	configparser.set(_eXoLoaderSection, _CollectionKey, collection)
	configparser.set(_eXoLoaderSection, _GameNameKey, eXoGameName)
	configparser.set(_eXoLoaderSection, _ArchiveKey, archive)
	with open(iniOutPath, 'w') as configfile: configparser.write(configfile)

def eXoImportDosBOXConf(dbConfInPath, dbConfOutPath):
	# Importing/Modifying the configuration
	logging.info(">>> Importing DosBOX configuration '" + dbConfInPath + "' into '" + dbConfOutPath + "'")
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

def eXoImportDesc(eXoGamedir, eXoIniPath, outputFile):
	logging.info(">>> Importing description...")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.read(eXoIniPath)
	
	# Read values
	about	= configparser.get("Main", "About")
	if about:
		filename = os.path.join(eXoGamedir, "Meagre", "About", about)
		if os.path.isfile(filename):
			shutil.copyfile(filename, outputFile)

def eXoCreateFile(filename, dir):
	# Importing/Modifying the configuration
	logging.info(">>> Creating eXoFile  '" + filename + "'")
	zipf = zipfile.ZipFile(filename, 'w')
	zipdir(dir, zipf)
	zipf.close()

def eXoImportGame(collection, eXoGamedir, eXoIniPath, doImportArtworks=False):
	# Init
	eXoGameName, eXoIniExt 	= os.path.splitext(os.path.basename(eXoIniPath))
	eXoDBConfPath 	= os.path.join(eXoGamedir, _DBConf)
	eXoArchiveFile 	= eXoGameName + ".zip"
	eXoArchivePath 	= os.path.join(eXoCollections[collection], _eXoGameDir, eXoArchiveFile)
	
	# Verifying DosBOX conf
	if not os.path.isfile(eXoDBConfPath):
		logging.error("DosBOX config file '" + eXoDBConfPath + "' not found in collection!")

	# Verifying archive
	if not os.path.isfile(eXoArchivePath):
		logging.error("Archive '" + eXoArchiveFile + "' not found in collection!")
		return
	
	# Creating temp dir
	tempDir = os.path.join(workingdir, timestamp())

	# Import game
	os.makedirs(tempDir)
	logging.info(">>> Importing game '" + eXoGameName + "'...")
	eXoImportIniFile(collection, eXoGameName, eXoArchiveFile, eXoIniPath, os.path.join(tempDir, _GameIni))
	eXoImportDosBOXConf(eXoDBConfPath, os.path.join(tempDir, _DBConf))
	eXoImportDesc(eXoGamedir, eXoIniPath, os.path.join(tempDir, _DescTxt))
	eXoCreateFile(os.path.join(gamesdir, eXoGameName + ".eXo"), tempDir)
	shutil.rmtree(tempDir)
	
	if doImportArtworks:
		eXoImportArts(eXoGamedir, eXoIniPath, eXoGameName)

def eXoImportCollection(collection, doImportArtworks=False):
	logging.info("<<< Importing '" + collection +"' collection >>>")

	if collection not in eXoCollections:
		print("Invalid collection '" + collection + "'!")
		sys.exit(1)

	if collection not in eXoArchives:
		print("Invalid archive for collection '" + collection + "'!")
		sys.exit(1)

	# Init
	eXoGamesArcPath	= eXoArchives[collection]
	
	# If archive not exists
	if not os.path.isfile(eXoGamesArcPath):
		print("'" + eXoGamesArcPath + "' not found!")
		sys.exit(1)
	
	# Creating temp dir
	tempDir = os.path.join(workingdir, timestamp())
	os.makedirs(tempDir)
	
	# Extract the archive
	logging.info("Found archive file '" + eXoGamesArcPath + "'. Extracting...")
	zfile = zipfile.ZipFile(eXoGamesArcPath)
	zfile.extractall(tempDir)
	zfile.close()
	
	# Processing informations
	collectiondir = os.path.join(tempDir, "!dos")
	for root, dirs, files in os.walk(collectiondir):
		for file in files:
			absfilepath = os.path.join(root, file)
			relfilepath = os.path.relpath(absfilepath, collectiondir)
			if ".ini" in relfilepath:
				logging.info("Found ini file '" + relfilepath + "'. Processing...")
				eXoRef		 	= relfilepath.split(os.sep)[0]
				eXoGamedir		= os.path.join(collectiondir, eXoRef)

				# Import
				eXoImportGame(collection, eXoGamedir, absfilepath, doImportArtworks)
	
	# Removing temp directory
	logging.info("Removing game directory...")
	shutil.rmtree(tempDir)

def eXoImportAllCollections(doImportArtworks=False):
	logging.info("<<< Importing all collections >>>")
	
	# For each collection
	for collection in eXoCollections.keys():
		eXoImportCollection(collection, doImportArtworks)

#*****************************************************************
#*****************************************************************
# Export Mode
#*****************************************************************
#*****************************************************************
def eXoExportLaunchbox(filename):
	logging.info(">>> Exporting collections to LaunchBox...")

def eXoExport(filename):
	logging.info("<<< Exporting collections >>>")


def main(argv):
	#*****************************************************************
	# Initialisation


	#*****************************************************************
	# Arguments
	mode 				= _NoMode
	doImportArtworks	= False
	romfile				= ""
	collection		= ""

	try:
	  opts, args = getopt.getopt(argv,"haIr:i:",["rom="])
	except getopt.GetoptError:
	  print(_eXoLauncherHelp)
	  sys.exit(2)
	for opt, arg in opts:
	  if opt == '-h':
		print(_eXoLauncherHelp)
		sys.exit()
	  elif opt in ("-r", "--rom"):
		mode = _LaunchMode
		romfile = arg
	  elif opt in ("-i", "--import"):
		mode = _ImportMode
		collection = arg
	  elif opt in ("-a", "--artworks"):
		doImportArtworks = True
	  elif opt in ("-I", "--importAll"):
		mode = _ImportAllMode

	# Launch mode
	if mode == _LaunchMode:
		# Launch the rom file
		eXoLaunch(romfile)
	elif mode == _ImportMode:
		# Import the collection
		eXoImportCollection(collection, doImportArtworks)
	elif mode == _ImportAllMode:
		# Import all the collections
		eXoImportAllCollections(doImportArtworks)
	else:
		print(_eXoLauncherHelp)
		sys.exit(2)

if __name__ == "__main__":
   main(sys.argv[1:])