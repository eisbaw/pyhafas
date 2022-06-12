import sys
import time
import datetime
import pytz

from pyhafas import HafasClient
from pyhafas.profile import RKRPProfile

lid_home = 'Strandboulevarden 95, 2100 København'
lid_work = {
    'Oticon'         : 'Kongebakken 9, 2765 Smørum',
    'EuropeanEnergy' : 'Gyngemose Parkvej 50, 2860 Søborg',
}


def time_delta_seconds(dt_from, dt_to):
    """ If 'dt_fromm' is ahead of 'dt_to', timedelta will assume modulo 1 day; avoid that """
    if dt_to >= dt_from:
        return (dt_to - dt_from).seconds
    else:
        return -((dt_from - dt_to).seconds)

def process_journeys(possibilities):
    time_now = datetime.datetime.now(pytz.timezone('Europe/Copenhagen'))
    list_seconds_until_dep = []

    print("\033c", end="")
    for p in possibilities:
        first = p.legs[0]
        last = p.legs[-1]
        route = []

        for l in p.legs:
            if l.name:
                lon_len = min(len(l.origin.name), 10)
                lon_short = l.origin.name[:lon_len].replace('(', '').replace(')', '').strip()
                #route += [str(l.name) + ' from ' + lon_short]
                route += [str(l.name)]

        time_seconds_to_departure = time_delta_seconds(dt_from=time_now, dt_to=first.departure)
        time_minutes_to_departure = time_seconds_to_departure/60.0

        print("In %5.1f min: %s -> %s (%s): %s" % (
                time_minutes_to_departure,
                first.departure.strftime('%H:%M'), 
                last.arrival.strftime('%H:%M'), 
                p.duration, 
                "; ".join(route)
            )
        )

        list_seconds_until_dep += [time_seconds_to_departure]

    return list_seconds_until_dep


try:
    lid_work_selected = lid_work[sys.argv[1]]
except Exception as e:
    print("Supply supported work id as argument")
    raise e


client = HafasClient(RKRPProfile(), debug=True)

# Lookup once
lid_home = client.locations(lid_home, rtype='ALL')[0].lid
lid_work_selected = client.locations(lid_work_selected, rtype='ALL')[0].lid

while True:
    # Issue new request
    possibilities = client.journeys(
        origin          = lid_home,
        destination     = lid_work_selected,
        date            = datetime.datetime.now(),
        min_change_time = 0,
        max_changes     = -1
    )

    # Process returned data and present it
    list_seconds_until_dep = process_journeys(possibilities)

    # We want to display up-to-date information without request-spamming.
    # I.e. we want to be nice towards rejseplanen but also accurate.
    # An adaptive way of doing that, would be to wait for expiry of the closest departure:
    # At that time, we should have new information available.
    earliest_dep = min(list_seconds_until_dep)
    # But if an update happens mid-way (e.g. cancellation), we would update too late.
    # So we shall have an oversampling factor to catch updates
    oversampling_factor = 2.0
    wait_until_next_query = earliest_dep / oversampling_factor
    # Should rejseplanen return a time waaay into the future incorrectly, let's not wait for that
    wait_until_next_query = min(wait_until_next_query, 1200)
    # Let us avoid spamming rejseplanen
    wait_until_next_query = max(wait_until_next_query, 60)
    
    for i in range(0, int(wait_until_next_query)):
        time.sleep(1)
        process_journeys(possibilities)        
        print("Next update in", wait_until_next_query-i, "seconds", end='', flush=True)
