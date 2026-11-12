import os
import sys
import re
import time
import json
import webbrowser
import subprocess
from datetime import datetime
import speech_recognition as sr   # pip install SpeechRecognition
import pyttsx3                    # pip install pyttsx3
import pyaudio                    # pip install pyaudio


# The standard sample rate (Hz) for speech recognition audio streams.
sampleRate = 500
# The maximum duration (in seconds) NOVA will wait for the wake word.
phraseTimeLimitWake = 2
# The maximum duration (in seconds) NOVA will wait for a command after waking up.
phraseTimeLimitCmd = 6

# A list of words or phrases that will activate the voice assistant.
wakeWords = ["hey nova", "nova"]

# The language code used for Googles STT transcription.
language = "en-GB"

# The time (in seconds) NOVA waits for a 'yes' or 'no' response during confirmation.
confirmationTimeout = 4

# The maximum number of times NOVA will reprompt the user if a command is unclear (not currently fully implemented).
maxNearMissReprompts = 1

# The file path where system events, errors, and task results will be logged.
logFile = "nova.log"

# Defines the capabilities and permissions required for core intents.
# This acts as a security check (e.g., 'open_file' needs 'read' permission).
permissions = {
    "open_file": {"read": True, "write": False, "delete": False},
    "search_web": {"net": True},
    "play_music": {"media": True},
}

# The core intent database. Maps an internal intent name (key) to a list of trigger phrases (values) used for Natural Language Processing.
intentDb = {
    "open_file": ["open file", "open", "launch file", "show file"],
    "search_web": ["search web", "search", "google", "look up"],
    "play_music": ["play music", "play song", "play", "start music"]
}

# A dictionary mapping synonyms to a standardised word.
# Used during the tokenisation process to normalise commands.
synonymsMap = {
    "launch": "open",
    "find": "search",
    "lookup": "search",
    "song": "music"
}

# Stores contextual information from previous commands to enable follow-up commands without repeating details.
context = {
    "last_file": None,
    "last_intent": None,
    "last_query": None,
    "last_song": None
}


# A list that stores log entries in memory for quick access during runtime.
systemLog = []  

# Function to record a system event both to memory and to nova.log
def logEvent(eventType, details):
    # Generate a timestamp for the log entry.
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create the log entry dictionary.
    entry = {
        "time": timestamp,
        "event": eventType,
        "details": details
    }

    # Append the dictionary entry to the in-program list.
    systemLog.append(entry)

    # Attempt to write the log entry to nova.log
    try:
        # Open the log file in append mode ("a") to add the new entry to the end.
        with open(logFile, "a", encoding="utf-8") as f:
            # Open the log file in append mode ("a") to add the new entry to the end, followed by a newline character for separation.
            f.write(json.dumps(entry) + "\n")

    # Handle exceptions if the file cannot be written.
    except Exception as e:
        # Print a warning to the console, as logging itself has failed.
        print("[LOG-ERROR] Could not write to log file: " + str(e))



try:
    # raise RuntimeError("This is a forced failure for testing")
    ttsEngine = pyttsx3.init() # "not an engine" # None   # Tries to create a TTS engine where ttsEngine is what points to the object to use to speak
except Exception as e:
    ttsEngine = None    # So the program knows there is no tts engine available
    print("[WARN] TTS engine failed to init: " + str(e))    # Prints a warning
    logEvent("WARN", "TTS init failed: " + str(e))  # Logs the error for testing uses

def speak(text): # Purpose is to say something out loud that something is "text"
    if text is None:
        text = ""   # Replaces text with an empty string
    try:
        if ttsEngine is not None:   # If the tts engine exists
            ttsEngine.say(text) # Queues the text to be spoken
            ttsEngine.runAndWait() # Gives the program time for the system to speak
        else:
            print("[Speech]: " + text)  # If it cant speak it will print it so theres some form of communication atleast
    except Exception as e:
        print("[Speech-Fallback]: " + text)
        logEvent("WARN", "TTS speak failed: " + str(e)) # If even the print fails the user is shown a warning and it is logged

def showVisualIndicator(state): # Purpose is to print a little marker to show NOVAs state
    marker = "[*] " # Default marker
    if state == "listening":
        marker = "[◉ Listening]"
    elif state == "processing":
        marker = "[… Processing]"
    elif state == "success":
        marker = "[✓ Success]"
    elif state == "error":
        marker = "[✗ Error]"
    print(marker)

def provideFeedback(taskResult):    # This is where both the speak and show visual indicator functions are used.
    try:
        status = taskResult.get("status", "error")  # Try to read the status from the results dictionary, default is error if the status is missing
        message = taskResult.get("message", "") # Try to read the message from the results dictionary, default is empty string if missing

        if status == "success":
            # Speak a confirmation message including the details.
            speak("Task completed: " + message)
            # Display the success visual indicator.
            showVisualIndicator("success")
            # Log the successful feedback event.
            logEvent("INFO", "Feedback success: " + message)

        else:
            # Check if the error message is empty (e.g., if the 'message' key was missing).
            if message == "":
                # Provide a generic error message if no specific message was found.
                message = "An error occurred."

            # Speak an error message including the details.
            speak("Error: " + message)
            # Display the error visual indicator.
            showVisualIndicator("error")
            # Log the failure event.
            logEvent("ERROR", "Feedback error: " + message)

    except Exception as e:
        # If the function fails, print the error and log it, as the primary feedback mechanism has failed.
        print("[Feedback error]: " + str(e))
        logEvent("ERROR", "ProvideFeedback exception: " + str(e))



recognizer = sr.Recognizer() # Creates single recogniser object from the sr library. It will hold settings like the threshold for sensitivity.

def listenOnce(timeLimit):  # Function to record one short audio and return it
    # Return format (audio or none, name of error or none)
    try:
        mic = sr.Microphone()
        # If the microphone has no input channels, treat it as unavailable
        p = pyaudio.PyAudio()
        if p.get_device_count() == 0:
            return None, "Mic error"
        p.terminate()

        with mic as source:  # Opens default microphone as audio source
            recognizer.adjust_for_ambient_noise(source, duration=1)  # Listens for a set length of time to estimate bg noise to change thresholds
            recognizer.energy_threshold = 19000  # Will set the difference between BG and Speech. Can and will need changing

            try:
                audio = recognizer.listen(source, timeout=timeLimit, phrase_time_limit=timeLimit)
                return audio, None  # If successful audio is returned and no error is given
                # Here is where the recording happens
                # Timeout is how long it will wait for speech to start before giving up
                # Phrase time limit is the length of the recording once the speaking starts, it will cut off the listening after this long
                # Returns the audio if successful
            except sr.WaitTimeoutError:
                return None, "timeout"
                # If no one speaks and timeout occurs nothing is returned and the error given is "timeout"

    except OSError:
        logEvent("ERROR", "Mic Error")
        return None, "Mic error"
        # For any case where there is no access to the microphone

    except Exception as e:
        logEvent("ERROR", "listenOnce exception: " + str(e))
        return None, "listen_error"
        # For anything other than a timeout or mic error, the event is logged and is given back as "listen error"



def transcribeAudio(audio, lang): # Function to return the audio as text

    # Returns format (audio as text or None, Is there an error in boolean)

    if audio is None:
        return "", True
        # Here if the audio is none then return an empty string and return that an error has occured, there is nothing usable
    try:
        text = recognizer.recognize_google(audio, language=lang)
        return text, False
        # Here, if there is audio then it is sent to googles stt recogniser and returned as text and no error (NOTE: INTERNET IS REQUIRED)
    except sr.UnknownValueError:
        print("Not understood")
        return "", True
        # Here google heard audio but didnt understand the words so empty string retuned and there is an error (NOTE: INTERNET IS REQUIRED)
    except sr.RequestError as e:
        logEvent("ERROR", "STT request error: " + str(e))
        return "", True
        # Here the STT did not work and so this can be reason to a lot of things one being internet problems, error is defined and logged
    except Exception as e:
        logEvent("ERROR", "STT exception: " + str(e))
        return "", True
        # Here the excoetion handling as always for any other prob;em there may have been


def detectWakePhrase(text): # Defines the function that will detect whether what is said is the wake word or not
    if text is None:
        return False
    # If nothing is said then the text will be None, returning false for no wake word, prevent errors arising because of the None after
    lower = text.lower().strip() # converts all the text to lowercase so it case-sensitive and 
                                 # then removes spaces at the start and front to avoid false negatives from accidental spaces
    for w in wakeWords: # loops through each word in the wake words list
        if w in lower: # checks to see if any of them are in the cariable "lower", if there is then it returns True
            return True
    return False


def tokenize(text): # Split text into normalised tokens (words)
    if text is None: # Handles missing input so no errors occur down the line
        return []
    lower = text.lower() # Convert to lowercase for a more cleaner process
    stripped = re.sub(r"[^a-z0-9\s\.\-_/']", " ", lower) # Replace disallowed characterss with spaces
    tokens = [t for t in stripped.split() if t != ""] # Split and remove empty tokens
    normalized = [] # Prepare normalised token list
    for t in tokens: # Loop through tokens
        normalized.append(synonymsMap.get(t, t)) # Replace synonyms if available
    return normalized # Return final tokens


def matchIntent(tokens): # Detect intent from tokens
    textJoin = " ".join(tokens) # Rejoin tokens for substring matching
    for intent, patterns in intentDb.items(): # Loop through intents
        for p in patterns: # Loop through patterns
            if p in textJoin: # Check if pattern is present in the users input
                return intent
    if "open" in tokens: # Fallback checks
        return "open_file"
    if "search" in tokens or "google" in tokens:
        return "search_web"
    if "play" in tokens:
        return "play_music"
    return "" # Unknown intent returns nothing


def extractParameters(intent, originalText): # Extract parameters based on intent
    params = {} # Store extracted values
    if originalText is None: # Nothing to parse
        return params
    text = originalText.strip() # Clean input for a more simpler process


    if intent == "open_file": # File intent handling
        m = re.search(r"'([^']+)'|\"([^\"]+)\"", text) # Look for quoted filename (mainly for typed up commands)
        if m:
            filename = m.group(1) if m.group(1) else m.group(2) # Extract filename
            params["filename"] = filename
        
        # Otherwise: capture everything after the words "open file"
        m2 = re.search(r"open\s+file\s+(.+)", text, re.IGNORECASE)
        if m2:
            params["filename"] = m2.group(1).strip()
            return params
        
        # Fallback: if user said just "open X"
        m3 = re.search(r"open\s+(.+)", text, re.IGNORECASE)
        if m3:
            params["filename"] = m3.group(1).strip()
            return params

        return params

    if intent == "search_web": # Search intent
        m = re.search(r"(search|google)\s+(for\s+)?(.+)", text, re.IGNORECASE) # Extract query with ignorecase allowing every version of the word to be used, meaning caps
        if m:
            params["keyword"] = m.group(3).strip()
        return params

    if intent == "play_music": # Music intent
        m = re.search(r"(play|start)\s+(music|song)?\s*(.+)?", text, re.IGNORECASE) # Extract song with ignorecase allowing every version to be used, meaning caps
        if m and m.group(3):
            params["song"] = m.group(3).strip()
        return params

    return params # Default empty params



# Checks if an intent has permission for a specific action
def checkPermission(intent, actionKey, path=None):
    caps = permissions.get(intent, {})              # Retrieves permission set for the intent
    allowed = caps.get(actionKey, False)            # Checks if actionKey is allowed
    if not allowed:                                 # If permission not granted, deny access
        return False
    if path is not None:                            # If a path is provided, validate it
        try:
            absHome = os.path.abspath(os.path.expanduser("~"))      # Gets absolute path of home dir
            absTarget = os.path.abspath(path)                       # Converts target to absolute path
            if not absTarget.startswith(absHome):                   # Denies access outside home dir
                return False
        except Exception as e:                                      # Handles unexpected path errors safely
            logEvent("ERROR", "Path safety check failed: " + str(e))
            return False
    return True                                     # Returns True if all checks pass

def needsConfirmation(intent):
    # Determines if an intent requires voice confirmation
    destructive = ["delete_file", "overwrite_file"]                 # List of potentially destructive intents
    return intent in destructive                                    # Returns True if confirmation is needed

def confirmActionViaVoice():
    # Asks the user to confirm an action using voice input
    speak("Are you sure? Please say yes or no.")                    # Prompts user to respond
    showVisualIndicator("listening")                                # Shows listening indicator
    audio, err = listenOnce(confirmationTimeout)                    # Listens once with a timeout
    if err is not None or audio is None:                            # Handles missing or failed input
        speak("I did not hear a response.")
        print("I did not hear a response.")
        return False
    text, flag = transcribeAudio(audio, language)                   # Converts audio to text
    if flag:                                                        # Handles failed transcription
        return False
    t = text.lower().strip()                                        # Cleans up the text
    if "yes" in t or "yeah" in t or "confirm" in t:                 # Returns True for positive confirmation
        return True
    if "no" in t or "nope" in t or "cancel" in t:                   # Returns False for negative confirmation
        return False
    return False                                                    # Default fallback if unclear response



def findFileInHome(filename):
    home_dir = os.path.expanduser("~")  # your home directory
    for root, dirs, files in os.walk(home_dir):
        if filename in files:
            return os.path.join(root, filename)  # full path to the file
    return None  # not found


def safeOpenPath(pathStr):
    if pathStr is None:
        return None
    
    # If pathStr looks like a relative path with folders or an absolute path, handle normally
    if os.path.sep in pathStr or pathStr.startswith("~") or pathStr.startswith("/"):
        path = os.path.expanduser(pathStr)
        path = os.path.abspath(path)
        if os.path.exists(path):
            return path
        else:
            return None
    
    # Otherwise pathStr is just a filename without folders, so search in home directory recursively
    found = findFileInHome(pathStr)
    return found



def openFile(params):
    # Opens a file if it exists and permission is granted
    filename = params.get("filename")                                           # Gets filename from parameters
    if not filename or filename.strip() == "":                                  # Checks if filename is missing
        return {"status": "error", "message": "No file name provided."}
   # print(f"DEBUG: filename = {filename}")
    path = safeOpenPath(filename)                                               # Validates and converts path
   # print(f"DEBUG: expanded path = {path}")

    if path is None:                                                            # Handles missing or invalid path
        return {"status": "error", "message": "File or path not found."}
    if not checkPermission("open_file", "read", path):                          # Checks permission to read file
        return {"status": "error", "message": "Permission denied for this path."}
    
    try:
        # Opens file based on the operating system
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
        context["last_file"] = path                                             # Saves last opened file in context
        return {"status": "success", "message": "Opened " + path}
    except Exception as e:                                                      # Catches and reports errors
        return {"status": "error", "message": "Failed to open: " + str(e)}

def searchWeb(params):
    # Performs a web search using the default browser
    keyword = params.get("keyword")                                             # Gets search keyword from parameters
    if not keyword or keyword.strip() == "":                                    # Checks for missing keyword
        return {"status": "error", "message": "No search keyword provided."}
    if not checkPermission("search_web", "net"):                                # Checks network permission
        return {"status": "error", "message": "Network permission denied."}
    try:
        url = "https://www.google.com/search?q=" + keyword.replace(" ", "+")    # Builds Google search URL
        webbrowser.open(url)                                                    # Opens browser to search page
        context["last_query"] = keyword                                         # Saves last query to context
        return {"status": "success", "message": "Searching the web for " + keyword}
    except Exception as e:                                                      # Handles web open failure
        return {"status": "error", "message": "Failed to open browser: " + str(e)}

def playMusic(params):
    # Plays a song locally or searches for it online
    song = params.get("song")                                                   # Gets song name from parameters
    if not checkPermission("play_music", "media"):                              # Checks permission to play media
        return {"status": "error", "message": "Media permission denied."}
    if not song or song.strip() == "":                                          # Handles case with no song name
        context["last_song"] = None
        return {"status": "success", "message": "Starting music player."}
    path = safeOpenPath(song)                                                   # Validates if song path exists
    try:
        if path is not None:                                                    # If valid local path, open it
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
            context["last_song"] = path                                         # Saves last song path to context
            return {"status": "success", "message": "Playing " + path}
        else:                                                                   # Otherwise search song on YouTube
            url = "https://www.youtube.com/results?search_query=" + song.replace(" ", "+")
            webbrowser.open(url)
            context["last_song"] = song                                         # Saves search keyword to context
            return {"status": "success", "message": "Searching for " + song}
    except Exception as e:                                                      # Handles playback errors
        return {"status": "error", "message": "Failed to play: " + str(e)}

def executeTask(intent, parameters):
    # Dispatches tasks to the correct handler function

    # DEBUG to see whats actually being taken in
    print("Intent = ", intent, "Params = ", parameters)

    taskMap = {
        "open_file": openFile,
        "search_web": searchWeb,
        "play_music": playMusic
    }
    if intent in taskMap:                                                       # Check if the intent is supported
        try:
            return taskMap[intent](parameters)                                  # Call the matching function with parameters
        except Exception as e:
            return {"status": "error", "message": "Task exception: " + str(e)}  # Return error if task execution fails
    return {"status": "error", "message": "Unsupported task."}                  # Return error if intent is not supported


def handleCommandFlow():
    showVisualIndicator("listening")     # Show that NOVA is now listening specifically for a command (after wake word)
    speak("I am listening for your command.")     # Auditory feedback to user indicating readiness
    audio, err = listenOnce(phraseTimeLimitCmd)   # Listen once for a short duration (phraseTimeLimitCmd) to capture the user’s actual command
    if err is not None or audio is None:          # If audio failed to record or the mic errored out, stop and notify the user
        provideFeedback({"status": "error", "message": "No command heard."})
        logEvent("ERROR", "Command listen failed: " + str(err))
        return                                    # Exit early
    text, flag = transcribeAudio(audio, language) # Convert spoken audio to text using STT
    if flag:                                      # If transcription failed, report the issue and exit
        provideFeedback({"status": "error", "message": "Could not understand the command."})  
        logEvent("ERROR", "STT error on command.")
        return
    logEvent("INFO", "Heard command: " + text)    # Log what NOVA heard
    tokens = tokenize(text)                       # Tokenise the text
    intent = matchIntent(tokens)                  # Try to determine the user's intent based on the tokens
    if intent == "":                              # If NOVA cannot match any intent, notify and exit
        provideFeedback({"status": "error", "message": "Unknown command."})
        logEvent("WARN", "Unknown intent for: " + text)
        return
    params = extractParameters(intent, text)      # Extract parameters relevant to the intent
    if intent == "open_file" and "filename" not in params and context["last_file"] is not None:
        params["filename"] = context["last_file"] # Reuse last referenced file
    if needsConfirmation(intent):
        ok = confirmActionViaVoice()              # Ask for a verbal yes/no
        if not ok:
            provideFeedback({"status": "error", "message": "Action cancelled."})
            logEvent("INFO", "User cancelled action for intent " + intent)
            return                                # User cancelled, do not execute task
    result = executeTask(intent, params)          # Execute the intent with extracted parameters

    # Catch unsupported intents and rewrite the error into a user-friendly message
    if result.get("status") == "error" and result.get("message", "").startswith("Unsupported"):
        result = {"status": "error", "message": "Intent '" + intent + "' is not supported."}
        logEvent("WARN", "Unsupported intent: " + intent)
    provideFeedback(result)                       # Provide verbal and visual feedback about the result of the command execution
    logEvent("TASK", {"intent": intent, "params": params, "result": result}) # Log the task

def mainLoop():
    speak("NOVA is online.")                      # Speak once on startup to confirm system is running
    logEvent("BOOT", "NOVA started")              # Log system boot event
    while True:                                   # NOVA will keep listening for the wake phrase until manually stopped
        try:
            showVisualIndicator("listening")      # Show idle listening state
            audio, err = listenOnce(phraseTimeLimitWake)  # Listen briefly for the wake phrase
            if err is None and audio is not None:         # Only continue if the microphone worked and some audio was captured
                text, flag = transcribeAudio(audio, language)  # Attempt to transcribe the potential wake phrase
                if not flag and detectWakePhrase(text):        # If transcription was successful AND text contains a valid wake phrase
                    showVisualIndicator("processing")          # Show that NOVA is now processing the input
                    speak("Yes?")                              # Verbal acknowledgment that NOVA heard the user
                    handleCommandFlow()                        # Now NOVA does it's thing
            time.sleep(0.1)
        except KeyboardInterrupt:                              # User manually pressed CTRL+C causes NOVA to shut down
            speak("Shutting down. Goodbye.")
            logEvent("SHUTDOWN", "User interrupt")
            break
        except Exception as e:                                 # Catch any runtime error to avoid crashing
            logEvent("ERROR", "Main loop exception: " + str(e))
            time.sleep(0.5)                                    # Rapid error looping is prevented by a short delay


if __name__ == "__main__":
    # Log the successful startup of the voice assistant.
    logEvent("INFO", "NOVA started.")
    # Begin the main processing loop where NOVA continuously listens for the wake word.
    mainLoop()
