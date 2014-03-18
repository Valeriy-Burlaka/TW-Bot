# Cookies of user's browser will be parsed to get session keys
# and spoof the game by acting like real user. Thus, real user
# can continue to play in parallel with farming bot and not to
# be superseded from his session.
BROWSER = ''

# Game host (e.g.: 'en73.tribalwars.net')
HOST = ''
HOST_SPEED = 1

# Set to True to disable time.sleep() calls inside the code
# (e.g. to run tests or to receive game-ban)
DEBUG = False

# Tribal Wars user data (account & password, needed to re-connect
# user when session expired
USER = ''
PASSWORD = ''

# Antigate service API key
ANTIGATE_KEY = ''

# How long bot should mock barbarians (hours)
FARM_DURATION = 1

FARM_FREQUENCY = 1

# X|Y coordinates of player's main village
BASE_X = 100
BASE_Y = 100
# Id of first user's village is needed as base point to perform
# some requests
MAIN_VILLAGE_ID = 10000

# Which villages should be used to farm resources
FARM_WITH = ()

TRUSTED_TARGETS = []
UNTRUSTED_TARGETS = []

# Whether defensive troops should be used to farm resources
USE_DEF_TO_FARM = False

# Whether Heavy Cavalry should be considered as def unit
HEAVY_IS_DEF = False

# Maximum allowed time for troops to leave their villages (hours)
T_LIMIT_TO_LEAVE = 4

# Test & source data location
DATA_FOLDER = 'bot/runtime_data'
TEST_DATA_FOLDER = 'bot/tests/test_data'

DATA_FILE = 'bot_data'
DATA_TYPE = 'local_file'
