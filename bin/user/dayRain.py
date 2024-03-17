import logging
import sys
import datetime
import time

from dataclasses import dataclass
from typing import Any, Dict, List

import weewx
import weewx.manager
import weeutil.logger


from weeutil.weeutil import timestamp_to_string
from weeutil.weeutil import to_bool
from weeutil.weeutil import to_float
from weeutil.weeutil import to_int
from weewx.engine import StdService

# get a logger object
log = logging.getLogger(__name__)

DAY_RAIN_VERSION = '0.01'

if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 7):
    raise weewx.UnsupportedFeature(
        "weewx-dayRain requires Python 3.7 or later, found %s.%s" % (sys.version_info[0], sys.version_info[1]))

if weewx.__version__ < "4":
    raise weewx.UnsupportedFeature(
        "weewx-dayRain requires WeeWX, found %s" % weewx.__version__)

# Set up dayRain observation type.
weewx.units.obs_group_dict['dayRain'] = 'group_rain'

@dataclass
class FutureDebit:
    timestamp: int
    amount   : float


class DayRain(StdService):
    def __init__(self, engine, config_dict):
        super(DayRain, self).__init__(engine, config_dict)
        log.info("Service version is %s." % DAY_RAIN_VERSION)

        if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 7):
            raise Exception("Python 3.7 or later is required for the dayRain plugin.")

        # Only continue if the plugin is enabled.
        dayRain_config_dict = config_dict.get('DayRain', {})
        enable = to_bool(dayRain_config_dict.get('enable'))
        if enable:
            log.info("DayRain is enabled...continuing.")
        else:
            log.info("DayRain is disabled. Enable it in the DayRain section of weewx.conf.")
            return

        self.total_rain: float = 0
        self.debit_list : List[FutureDebit] = []
        self.initialized = False

        self.bind(weewx.PRE_LOOP, self.pre_loop)
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop)

    def pre_loop(self, event):
        if self.initialized:
            return
        self.initialized = True

        try:
            binder = weewx.manager.DBBinder(self.config_dict)
            binding = self.config_dict.get('StdReport')['data_binding']
            dbm = binder.get_manager(binding)
            # Get the column names of the archive table.
            archive_columns: List[str] = dbm.connection.columnsOf('archive')

            # Get archive records to prime 24h rainfall.
            today = datetime.date.today()
            earliest_time: int = to_int(time.mktime(today.timetuple()))
            log.debug('Earliest time selected is %s' % timestamp_to_string(earliest_time))

            # Fetch the records.
            start = time.time()
            archive_pkts: List[Dict[str, Any]] = DayRain.get_archive_packets(
                dbm, archive_columns, earliest_time)

            # Save packets as appropriate.
            pkt_count = 0
            one_day_later = earliest_time + 86400
            for pkt in archive_pkts:
                if 'rain' in pkt and pkt['rain'] is not None and pkt['rain'] > 0.0:
                    self.total_rain += pkt['rain']
                    self.debit_list.append(FutureDebit(timestamp = one_day_later, amount = pkt['rain']))
                    pkt_count += 1
            log.debug('Collected %d archive packets containing rain in %f seconds.' % (pkt_count, time.time() - start))
        except Exception as e:
            # Print problem to log and give up.
            log.error('Error in DayRain setup.  DayRain is exiting. Exception: %s' % e)
            weeutil.logger.log_traceback(log.error, "    ****  ")

    @staticmethod
    def massage_near_zero(val: float)-> float:
        if val > -0.0000000001 and val < 0.0000000001:
            return 0.0
        else:
            return val

    @staticmethod
    def get_archive_packets(dbm, archive_columns: List[str],
            earliest_time: int) -> List[Dict[str, Any]]:
        packets = []
        for cols in dbm.genSql('SELECT * FROM archive' \
                ' WHERE dateTime > %d ORDER BY dateTime ASC' % earliest_time):
            pkt: Dict[str, Any] = {}
            for i in range(len(cols)):
                pkt[archive_columns[i]] = cols[i]
            packets.append(pkt)
            log.debug('get_archive_packets: pkt(%s): %s' % (
                timestamp_to_string(pkt['dateTime']), pkt))
        return packets

    def new_loop(self, event):
        pkt: Dict[str, Any] = event.packet
        pkt_time: int       = to_int(pkt['dateTime'])

        assert event.event_type == weewx.NEW_LOOP_PACKET
        log.debug(pkt)

        # Process new packet.
        # Be careful, the first time through, pkt['rain'] may be none.
        if 'rain' in pkt and pkt['rain'] is not None and pkt['rain'] > 0.0:
            pkt_time = pkt['dateTime']
            pkt_dt = datetime.datetime.fromtimestamp(to_int(pkt_time))
            one_day_later = to_int(time.mktime(pkt_dt.replace(hour=0, minute=0, second=0).timetuple())) + 86400
            self.total_rain += pkt['rain']
            self.debit_list.append(FutureDebit(timestamp = one_day_later, amount = pkt['rain']))
            log.debug('found rain of %f, adding to dayRain.' % pkt['rain'])

        # Debit and remove any debits that have matured.
        del_count: int = 0
        for debit in self.debit_list:
            if to_float(debit.timestamp) <= pkt_time:
                log.debug('debiting rain by %f' % debit.amount)
                del_count += 1
                self.total_rain -= debit.amount
                # We're dealing with floating point, we don't want to see a -0.0
                if self.total_rain < 0.0:
                    self.total_rain = 0.0
            else:
                break
        for i in range(del_count):
            log.debug('process_queue: Deleting matured debit(%s)' % timestamp_to_string(
                debit.timestamp))
            del self.debit_list[0]

        # Add dayRain to packet
        pkt['dayRain'] = DayRain.massage_near_zero(self.total_rain)
        log.debug('new_loop: Added pkt[dayRain] of %f' % self.total_rain)
