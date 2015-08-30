# coding=UTF-8
import zipfile
from zipfile import BadZipfile
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

#*****************************************************************
#*****************************************************************
# Tools
#*****************************************************************
#*****************************************************************
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
			logging.debug("Archiving file : " + relfilepath)
			ziph.write(absfilepath, relfilepath)

def searchFileInDirectories(dirs = [], filename = ""):
	# For each directory
	for dir in dirs:
		if os.path.isdir(dir):
			path = os.path.join(dir, filename)
			if os.path.isfile(path):
				return path

#*****************************************************************
# Constants
_Name				= "eXoLauncher"
_Version			= 0.2
_eXoLauncherHelp 	= "Usage : eXoLauncher.py -r <eXo file>"

# Mode
_NoMode				= 0
_LaunchMode			= 1
_ImportMode			= 2

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
	# Initialisation
	logging.debug("<<< Initialisation >>>")

	# Setting up directories
	gamedir 	= os.path.join(workingdir, timestamp())
	savepath 	= os.path.join(savesdir, gamename + ".zip")
	gamedbconf	= os.path.join(gamedir, _DBConf)

	# Logging
	logging.debug("Game directory : '" + gamedir + "'")
	logging.debug("Savegame : '" + savepath + "'")
	logging.debug("Dosbox config file : '" + gamedbconf + "'")

	#*****************************************************************
	# Pre-processing
	logging.debug("<<< Pre-processing >>>")

	# Creating game directory
	os.makedirs(gamedir)

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
	shutil.rmtree(gamedir)

#*****************************************************************
#*****************************************************************
# Convert Mode
#*****************************************************************
#*****************************************************************
def importRenameFile(src, name, dstDir):
	filename, fileext 	= os.path.splitext(src)
	dstname				= name + fileext
	dst					= os.path.join(dstDir, dstname)
	shutil.copyfile(src, dst)

def eXoConvertArts(eXoGamedir, eXoIniPath, eXoGameName, outputDirs):
	logging.debug("Converting artworks '" + eXoGameName + "'...")
	
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.read(eXoIniPath)
	
	# Read values
	front 		= configparser.get("Main", "Front01")
	back		= configparser.get("Main", "Back01")
	title		= configparser.get("Main", "Title01")
	screenshot	= configparser.get("Main", "Screen01")

	# If valid
	if front:
		filename = os.path.join(eXoGamedir, _Meagre, "Front", front)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, outputDirs[_FrontsDir])
	if back:
		filename = os.path.join(eXoGamedir, _Meagre, "Back", back)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, outputDirs[_BacksDir])
	if title:
		filename = os.path.join(eXoGamedir, _Meagre, "Title", title)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, outputDirs[_TitlesDir])
	if screenshot:
		filename = os.path.join(eXoGamedir, _Meagre, "Screen", screenshot)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, outputDirs[_ScreensDir])

def eXoConvertManual(eXoGamedir, eXoIniPath, eXoGameName, outputDirs):
	logging.debug("Converting manual '" + eXoGameName + "'...")
	
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.read(eXoIniPath)
	
	# Read values
	manual		= configparser.get("Main", "Manual")

	# If valid
	if manual:
		filename = os.path.join(eXoGamedir, _Meagre, "Manual", manual)
		if os.path.isfile(filename):
			importRenameFile(filename, eXoGameName, outputDirs[_ManualsDir])

def eXoConvertIniFile(eXoGameName, archive, iniInPath, iniOutPath):
	logging.debug("Converting ini file '" + iniInPath + "' into '" + iniOutPath + "'")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.read(iniInPath)
	configparser.set(_eXoLoaderSection, _GameNameKey, eXoGameName)
	configparser.set(_eXoLoaderSection, _ArchiveKey, archive)
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

def eXoConvertDesc(eXoGamedir, eXoIniPath, outputFile):
	logging.debug("Converting description...")
	configparser = ConfigParser.ConfigParser()
	configparser.optionxform=str # For case sensitiveness
	configparser.read(eXoIniPath)
	
	# Read values
	about	= configparser.get("Main", "About")
	if about:
		filename = os.path.join(eXoGamedir, _Meagre, "About", about)
		if os.path.isfile(filename):
			shutil.copyfile(filename, outputFile)

def eXoCreateFile(filename, dir):
	logging.debug("Creating eXoFile  '" + filename + "'...")
	zipf = zipfile.ZipFile(filename, 'w')
	zipdir(dir, zipf)
	zipf.close()

def eXoConvertGame(dir, eXoRef, eXoGameName, outputDirs):
	logging.info("Converting game '" + eXoGameName + "'...")
	eXoGameDir		= os.path.join(dir, eXoRef)
	eXoArchiveFile 	= eXoGameName + ".zip"
	
	# Verifying Ini file
	eXoIniPath 	= os.path.join(eXoGameDir, _Meagre, "IniFile", eXoGameName + ".ini")
	if not os.path.isfile(eXoIniPath):
		logging.warning("Ini file '" + eXoIniPath + "' not found for " + eXoGameName + "! -> Skipping")

	# Verifying DosBOX conf
	eXoDBConfPath 	= os.path.join(eXoGameDir, _DBConf)
	if not os.path.isfile(eXoDBConfPath):
		logging.warning("DosBOX config file '" + eXoDBConfPath + "' not found for " + eXoGameName + "! -> Skipping")

	# Verifying archive
	eXoArchivePath	= searchFileInDirectories(eXoCollections, eXoArchiveFile)
	if not eXoArchivePath:
		logging.warning("No archive '" + eXoArchiveFile + "' found in any collection! -> Skipping")
		return
	
	# Creating temp dir
	tempDir = os.path.join(workingdir, timestamp())

	# Convert game
	os.makedirs(tempDir)
	eXoConvertIniFile(eXoGameName, eXoArchiveFile, eXoIniPath, os.path.join(tempDir, _GameIni))
	eXoConvertDosBOXConf(eXoDBConfPath, os.path.join(tempDir, _DBConf))
	eXoConvertDesc(eXoGameDir, eXoIniPath, os.path.join(tempDir, _DescTxt))
	eXoCreateFile(os.path.join(outputDirs[_GamesDir], eXoGameName + ".eXo"), tempDir)
	shutil.rmtree(tempDir)
	
	# Convert artworks
	if _FrontsDir in outputDirs:
		eXoConvertArts(eXoGameDir, eXoIniPath, eXoGameName, outputDirs)

	# Convert manual
	if _ManualsDir in outputDirs:
		eXoConvertManual(eXoGameDir, eXoIniPath, eXoGameName, outputDirs)

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

	# Process
	for root, dirs, files in os.walk(dir):
		for file in files:
			if ".ini" in file:
				logging.debug("Found ini file '" + file + "'. Processing...")
				absfilepath 			= os.path.join(root, file)
				relfilepath 			= os.path.relpath(absfilepath, eXoDir)
				eXoRef		 			= relfilepath.split(os.sep)[0]
				eXoGameName, eXoIniExt 	= os.path.splitext(os.path.basename(file))

				# Convert
				eXoConvertGame(eXoDir, eXoRef, eXoGameName, outputDirs)

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
	tempDir = os.path.join(workingdir, timestamp())
	os.makedirs(tempDir)

	# Convert
	logging.info("Extracting archive file '" + eXoGamesArcPath + "'...")
	archive.extractall(tempDir)
	
	# Convert directory
	eXoConvertDir(tempDir, outputDirs)
	
	# Removing temp directory
	logging.info("Removing temporary directory...")
	shutil.rmtree(tempDir)

def eXoConvertCollection(collection, outputDirs, doImportArtworks, doImportManuals):
	# According to parameter (file/directory)
	if os.path.isfile(collection):
		# Convert archive
		eXoConvertArchive(collection, outputDirs)
	elif os.path.isdir(collection):
		# Convert directory
		eXoConvertDir(collection, outputDirs)
	else:
		logging.error("File '" + collection + "' not found!")
		return(1)

def eXoImportCollection(collection, outputDir, doImportArtworks, doImportManuals):
	# Game dir
	outputDirs = dict()
	outputDirs[_GamesDir] = os.path.join(outputDir, _GamesDir)
	
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
		if not os.path.isdir(dir): 
			os.makedirs(dir)

	# Convert collection
	eXoConvertCollection(collection, outputDirs, doImportArtworks, doImportManuals)

#*****************************************************************
#*****************************************************************
# Export Mode
#*****************************************************************
#*****************************************************************
def eXoExportLaunchbox(filename):
	logging.info("Exporting collections to LaunchBox...")

def eXoExport(filename):
	logging.info("<<< Exporting collections >>>")

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
	  opts, args = getopt.getopt(argv,"hamr:i:o:",["rom="])
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
			logging.error("You must provides an output directory -o)!")
			sys.exit(2)
		# Convert the collection
		eXoImportCollection(collection, outputDir, doImportArtworks, doImportManuals)
	else:
		logging.info(_eXoLauncherHelp)
		sys.exit(2)

if __name__ == "__main__":
   main(sys.argv[1:])