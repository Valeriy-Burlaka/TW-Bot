# Cookies of user's browser will be parsed to get session keys
# and spoof the game by acting like real user. Thus, real user
# can continue to play in parallel with farming bot and not to
# be superseded from his session.
BROWSER = 'Chrome'
# Game host
HOST = 'en70.tribalwars.net'
# Tribal Wars user data (account & password, needed to re-connect
# user when session expired
USER = 'Chebutroll'
PASSWORD = 'cjiy47H5MamVephlVddV'
# Antigate service API key
ANTIGATE_KEY = 'bd676a60b996da118afcb2f12f3182e0'
# How long bot should mock barbarians (hours)
FARM_DURATION = 24
# X|Y coordinates of player's main village
BASE_X = 211
BASE_Y = 305
MAIN_VILLAGE_ID = 127591
# Which villages should be used to farm resources
FARM_WITH = (127591,  # matriarch
             126583,  # piles
             124332,  # camp
             135083,  # cave
             136409,  # feast
             135035,  # lounge
             136329,  # shame
             127349,  # revenge
             128145,  # hive
             132326)  # voodoo
# Whether defensive troops should be used to farm resources
USE_DEF_TO_FARM = False
# Whether Heavy Cavalry should be considered as def unit
HEAVY_IS_DEF = False
# Maximum allowed time for troops to leave their villages (hours)
T_LIMIT_TO_LEAVE = 4
# Where to store information about sent attacks between bot's sessions
OBSERVER_FILE = 'test_observer_data'
# Uncomment this setting if you wish to post attack id numbers to
# tribal forum
SUBMIT_ID_INFO = {"forum_id": 37442,
                  "thread_id": 135582,
                  "frequency": 1500,  # seconds
                  "delay": 300}    # seconds
if SUBMIT_ID_INFO:
    SUBMIT_IDS = SUBMIT_ID_INFO
else:
    SUBMIT_IDS = False

# Test & source data location
MAP_DATA_FOLDER = 'bot/runtime_data/map'
HTML_TEST_DATA_FOLDER = 'bot/tests/test_data/html'