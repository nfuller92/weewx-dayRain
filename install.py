import sys
import weewx
from setup import ExtensionInstaller

def loader():
    if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 7):
        sys.exit("weewx-dayRain requires Python 3.7 or later, found %s.%s" % (
            sys.version_info[0], sys.version_info[1]))

    if weewx.__version__ < "4":
        sys.exit("weewx-dayRain requires WeeWX 4, found %s" % weewx.__version__)

    return DayRainInstaller()

class DayRainInstaller(ExtensionInstaller):
    def __init__(self):
        super(DayRainInstaller, self).__init__(
            version = "0.01",
            name = 'dayRain',
            description = 'Inserts dayRain observations into loop packets.',
            author = "Nate Fuller",
            author_email = "njfuller50@gmail.com",
            data_services = 'user.dayRain.DayRain',
            config = {
                'DayRain': {
                    'enable':'true',
                },
            },
            files = [
                ('bin/user', [
                    'bin/user/dayRain.py',
                    ]),
            ])
