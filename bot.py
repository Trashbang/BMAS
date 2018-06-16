import os
import ctypes
import tweepy
import markovify
import random
import ffmpy
import wave
import time
import datetime
import pywintypes
import win32evtlog
import mwapi
import json
from secrets import *
from time import gmtime, strftime, localtime


# ====== Individual bot configuration ==========================
bot_username = 'BMRF_ALERTS'
logfile_name = bot_username + ".log"

# ==============================================================

# Non-speech elements (i.e. should not be part of readable output

noises = ("bizwarn", "bloop", "buzwarn", "buzzwarn", "dadeda", "deeoo", "doop", "woop")

# Files containing these should be ignored completely (why are they even here???)
ignoreFiles = ("asay", "endgame", "gotquad", "sack", "sreq", "ssay", "voxlogin")

def classify_vocabulary(words):
	# Take a list of all the words spoken by the system and classify them (noun, adj, etc).
	# This will allow us to augment the Markov chain model by drawing parallels between words that
	# can be potentially swapped out while still retaining grammatical sanity.
	
	# The applicable types of word, as defined by Wiktionary, are:
	# - en-adj (adjectives)
	# - en-adv (adverbs)
	# - en-con (conjunctions)
	# - en-noun (noun)
	# - en-proper noun (proper nouns, like names)
	# - en-pron (pronouns)
	# - en-verb (verbs)
	
	# Start a Wiktionary session so we can utilise its services
	session = mwapi.Session("https://en.wiktionary.org")
	
	wordsList = words.split("\n")
	queryWords = ""
	pages = []
	
	# The MediaWiki API only lets us pull up to fifty pages at a time, so we need to break this up into a few queries
	for wordIdx in range(len(wordsList) - 1): # it's counterintuitive, but we gotta track the index for modulus
		queryWords = queryWords + "|" + wordsList[wordIdx]
		if (((wordIdx + 1) % 50 == 0) or (wordIdx + 1) == len(wordsList)): # Only once every fifty words, or when we reach the end
			# Check https://www.mediawiki.org/wiki/API and https://pythonhosted.org/mwapi
			# if you really gotta know how this query is put together.
			# Bottom line is that we're looking up all the pages with the titles in queryWords,
			# then pulling down the page contents
			query = session.get(action='query', prop='revisions', rvprop='content', format='json', formatversion='2', titles=queryWords)
			pages.append(query['query']['pages']) # The actual pages are buried a little bit into the json 
			queryWords = ""

	# Go through pages and get word definitions
	for page in pages:
		word = page['title']
		pageContent = page['revisions'][0]['content'] # Grab the content of the most recent revision (a.k.a the only revision we pulled)
		
		# Okay, here's where it gets messy.
		# Wikitext is non-hierarchical. Thus, our best hope for getting the ENGLISH definition of the word
		# is to look for headings of the form "==English==\n", then try to pull out everything between them
		# and the next heading of the same form (or the end of the content, whatever comes first)
	
	

def create_model():
	# get the list of (canonical) sentences spoken by vox
	sentencesFile = open("sentences.txt", "r")
	sentences = sentencesFile.read()
	
	# train main model
	mainModel = markovify.NewlineText(sentences, 2)
	
	# get list of all potential words (some of these don't appear in the game at all 
	# but I wanna use them cuz they're neat)
	wordsFile = open("words.txt", "r")
	words = wordsFile.read()
	wordsList = words.split("\n")
	
	# create a series of 'sentences' consisting of random word combinations
	# the goal here is to create (very weak) links between some words
	# in order to introduce an element of chaos to the model
	combos = ""
	for i in range(500):
		nextSentence = ""
		for j in range(6):
			nextSentence = nextSentence + wordsList[random.randrange(len(wordsList))] + " "
		combos = combos + nextSentence + "\n"
	print("Size of primary model: " + str(len(sentences)))
	print("Size of secondary model: " + str(len(combos)))
		
	# train secondary model
	secondaryModel = markovify.NewlineText(combos)
	
	# merge models, make sure to give appropriate weighting	
	completeModel = markovify.combine([mainModel, secondaryModel], [1.0, 0.2])
	
	return completeModel

def create_tweet(model):
	
	# generate sentence from supplied markov model (model may produce None if it fails)
	sentenceText = None
	isValid = False
	while (isValid is False):	
		sentenceText = model.make_short_sentence(200)
		if (sentenceText is not None):
			isValid = True
			
	# randomly replace a small percentage of words, for b-b-b-bonus chaos
	wordsFile = open("words.txt", "r")
	words = wordsFile.read()
	wordsList = words.split("\n")
	sentenceWords = sentenceText.split(" ")
	sentenceText = ""
	for word in sentenceWords:
		if (random.random() < 0.02):
			sentenceText = sentenceText + wordsList[random.randrange(0, len(wordsList)-1)] + " "
		else:
			sentenceText = sentenceText + word + " "
	
	# clean up text presentation
	niceText = sentenceText.upper()
	niceText = niceText.replace(" _COMMA", ",")
	for noise in noises:
		niceText = niceText.replace(noise.upper(), "")
	niceText = niceText.replace("  ", " ")
	niceText = niceText.replace(" ,", "")
	niceText = niceText.strip(", ")
	niceText = "[ " + niceText + " ]"
	sentenceText = sentenceText.strip(", ")
	print(sentenceText)
	print(niceText)
	
	# concatenate the wavs together	
	
	wavParams = []
	wavFrames = []
	audioFilenames = sentenceText.split(" ")
	for audioFilename in audioFilenames:
		audioFilename = "D:/Games/Steam/steamapps/common/Half-Life/valve/sound/vox/" + audioFilename + ".wav"
		audioFile = wave.open(audioFilename, "rb")
		wavParams.append(audioFile.getparams())
		wavFrames.append(audioFile.readframes(audioFile.getnframes()))
		audioFile.close()
	
	concWav = wave.open("D:/Games/Steam/steamapps/common/Half-Life/valve/sound/vox/_BMAS_concat.wav", 'wb')
	concWav.setparams(wavParams[0]) # we can only set params once, so just make it the first one we pick
	for i in range(len(wavFrames)):
		concWav.writeframes(wavFrames[i])
	concWav.close()
	
	# pair the audio with a still frame so we can upload it as a video (fuck you, twitter)
	backgrounds = os.listdir("backgrounds/")
	index = random.randint(0, len(backgrounds) - 1)
	background = backgrounds[index]
	
	vidPath = "output/output.mp4"
	
	inputFiles = {"backgrounds/" + background:None, "D:/Games/Steam/steamapps/common/Half-Life/valve/sound/vox/_BMAS_concat.wav":None}
	outputFiles = {vidPath:"-acodec aac -vcodec libx264 -shortest"}
	params = "-y -loop 1"
	ff = ffmpy.FFmpeg(global_options=params, inputs=inputFiles, outputs=outputFiles)
	ff.run()
		
	return niceText, vidPath

def tweet(text, vidPath):
	# Twitter authentication
	auth = tweepy.OAuthHandler(C_KEY, C_SECRET)
	auth.set_access_token(A_TOKEN, A_TOKEN_SECRET)
	api = tweepy.API(auth)

    # Send the tweet and log success or failure
	try:
		print("Uploading video...")
		media = api.upload_chunked(vidPath)
		print("Video uploaded, sleeping for ten seconds to avoid a Twitter bug =_=;...")
		time.sleep(10)
		print("Posting...")
		api.update_status(status=text, media_ids=[media.media_id])
		print("Posted!")
		pass
	except tweepy.error.TweepError as e:
		log(e.message)
	else:
		log("\nTweeted: " + text)


def log(message):
    """Log message to logfile."""
    path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    with open(os.path.join(path, logfile_name), 'a+') as f:
        t = strftime("%d %b %Y %H:%M:%S", localtime())
        f.write("\n" + t + " " + message)

def justWokeUp():
	justWokeUp = False
	# crack open the windows event logs and see if we woke up less than X minutes ago
	server = 'localhost'
	logtype = 'System'
	log = win32evtlog.OpenEventLog(server, logtype)
	
	foundPowerEvent = False
	readFlags = win32evtlog.EVENTLOG_BACKWARDS_READ|win32evtlog.EVENTLOG_SEQUENTIAL_READ # read backwards in order
	wakeTime = ""
	
	# get most recent power event
	while (not(foundPowerEvent)): 
		events = win32evtlog.ReadEventLog(log, readFlags, 0) # 0 is the offset, don't bother with it
		for event in events:
			if (event.SourceName == "Microsoft-Windows-Power-Troubleshooter"):
				wakeTime = event.TimeGenerated
				foundPowerEvent = True
				break
	
	niceWakeTime = datetime.datetime.strptime(str(wakeTime), "%Y-%m-%d %H:%M:%S")
	timeNow = datetime.datetime.today()
	timeDifference = timeNow - niceWakeTime
	timeDifference = timeDifference.total_seconds()
	
	print (timeDifference)
	
	if (timeDifference < 300): # you've got five minutes to do your job, pal
		justWokeUp = True
		
	return justWokeUp

def nitenite():
	# go to sleep, sweet prince	
	ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
		
if __name__ == "__main__":
	try:
		random.seed()
		model = create_model()
		text, vidPath = create_tweet(model)
		tweet(text, vidPath)
	except Exception as e:
		log("\n" + e.message + "\n")
	if (justWokeUp()):
		nitenite()