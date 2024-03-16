# weewx-dayRain
*Open source plugin for WeeWX software.

Modification of rain24h by John A Kline (john@johnkline.com)

**This extension requires Python 3.7 or later and WeeWX 4.**


## Description

dayRain is a modified version of Rain24h (plugin for weewx) that inserts rainfall totals since midnight into loop packets.
The rainfall since midnight is available in reports as `$current.dayRain`

## Why require Python 3.7 or later?

dayRain code includes type annotation which do not work with Python 2, nor in
earlier versions of Python 3.


## Licensing

weewx-dayRain is licensed under the GNU Public License v3.