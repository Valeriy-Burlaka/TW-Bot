import sys
import os
import logging

from bot.app.bot import Bot


def main(arguments):
    platform = sys.platform
    if platform not in ('linux', 'win32'):
        print("Sorry, but Bot knows nothing about your OS"
              "(only Windows & Linux platforms are currently supported)")
        sys.exit(1)
    try:
        import settings
    except ImportError:
        print("Settings file was not found")
        sys.exit(1)

    logging_level = 20  # INFO
    if len(arguments) > 1:
        numeric_log_level = getattr(logging, arguments[1].upper(), None)
        if isinstance(numeric_log_level, int):
            logging_level = numeric_log_level
        else:
            print("Received unknown logging level as first argument."
                  "Using WARNING level instead")

    logfile = os.path.join(settings.DATA_FOLDER, 'log.txt')
    logging.basicConfig(filename=logfile, level=logging_level,
                        format='%(asctime)s: %(levelname)s: %(message)s',
                        datefmt='%d/%b/%Y %H:%M:%S %Z %z')
    try:
        bot = Bot()
        logging.info("Starting to loot barbarians")
        bot.start()
        bot.join()
    finally:
        logging.info("Finishing to loot barbarians")
        bot.stop()
        sys.exit()


if __name__ == '__main__':
    try:
        main(sys.argv)
    except UnboundLocalError:
        logging.error("Bot has died before it's birth!")
    except SystemExit:
        print("Exiting now")
        os._exit(1)