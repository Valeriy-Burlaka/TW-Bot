# Cookies of user's browser will be parsed to get session keys
# and spoof the game by acting like real user. Thus, real user
# can continue to play in parallel with farming bot and not to
# be superseded from his session.
BROWSER = 'Chromium'

# Game host
HOST = 'en73.tribalwars.net'
HOST_SPEED = 1.5

# Set to True to disable time.sleep() calls inside the code
# (e.g. to run tests or to receive game-ban)
DEBUG = False

# Tribal Wars user data (account & password, needed to re-connect
# user when session expired
USER = 'ProperBill'
PASSWORD = 'pO3O09YXXOlHw6Dpucl6'

# Antigate service API key
ANTIGATE_KEY = 'bd676a60b996da118afcb2f12f3182e0'

# How long bot should mock barbarians (hours)
FARM_DURATION = 1

FARM_FREQUENCY = 3

# X|Y coordinates of player's main village
BASE_X = 504
BASE_Y = 306
# Id of first user's village is needed as base point to perform
# some requests
MAIN_VILLAGE_ID = 41940

# Which villages should be used to farm resources
FARM_WITH = (41940,)

TRUSTED_TARGETS = []

# Whether defensive troops should be used to farm resources
USE_DEF_TO_FARM = False

# Whether Heavy Cavalry should be considered as def unit
HEAVY_IS_DEF = False

# Maximum allowed time for troops to leave their villages (hours)
T_LIMIT_TO_LEAVE = 3

# Uncomment this setting if you wish to post attack id numbers to
# tribal forum
# SUBMIT_ID_INFO = {"forum_id": 37442,
#                   "thread_id": 135582,
#                   "frequency": 1500,  # seconds
#                   "delay": 300}    # seconds
# if SUBMIT_ID_INFO:
#     SUBMIT_IDS = SUBMIT_ID_INFO
# else:
#     SUBMIT_IDS = False

# Test & source data location
DATA_FOLDER = 'bot/runtime_data'
TEST_DATA_FOLDER = 'bot/tests/test_data'

DATA_FILE = 'bot_data'
DATA_TYPE = 'local_file'
