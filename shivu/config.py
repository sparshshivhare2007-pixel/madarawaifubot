class Config(object):
    LOGGER = True

    # Get this value from my.telegram.org/apps
    OWNER_ID = "7641508639"
    sudo_users = "7641508639", "7641508639"
    GROUP_ID = -1003773882799
    TOKEN = "8821944749:AAERuFlZmsQ191GL8HOagSgtGYSkAMzaBL0"
    mongo_url = "mongodb+srv://HaremDBBot:ThisIsPasswordForHaremDB@haremdb.swzjngj.mongodb.net/?retryWrites=true&w=majority"
    PHOTO_URL = ["https://telegra.ph/file/b925c3985f0f325e62e17.jpg", "https://telegra.ph/file/4211fb191383d895dab9d.jpg"]
    SUPPORT_CHAT = "NezukoWaifuRobot"
    UPDATE_CHAT = "NezukoWaifuRobot"
    BOT_USERNAME = "NezukoWaifuRobot"
    CHARA_CHANNEL_ID = "-1003773882799"
    api_id = 26626068
    api_hash = "bf423698bcbe33cfd58b11c78c42caa2"

    
class Production(Config):
    LOGGER = True


class Development(Config):
    LOGGER = True
