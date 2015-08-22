import lib.event
import lib.irc
import settings
import logging
import time
import MySQLdb


SENSORS_STATE = dict()
SENSORS = list()
UPDATE_TICK_COUNTER = 0
UPDATE_TICK_COUNTER_THRESHOLD = 3
_log = logging.getLogger(__name__)


class Sensor:

    def __init__(self):
        self.sensor_id = None
        self.description = None
        self.last_state_updated = None
        self.state = None

        # flag that marks this object as checked
        # (is used to verify if this object is still connected to the server)
        self.checked = False


@lib.cmd.command()
def sensors(msg):
    """Outputs sensors information."""

    global SENSORS

    output_msg = ""
    if len(SENSORS) == 0:
        output_msg = "No sensor data."
    else:
        for sensor in SENSORS:

            time_struct = time.localtime(sensor.last_state_updated)

            output_msg += str(time_struct.tm_mday) + "." + \
                str(time_struct.tm_mon) + "." + \
                str(time_struct.tm_year) + "/" + \
                str(time_struct.tm_hour) + ":" + \
                str(time_struct.tm_min) + ":" + \
                str(time_struct.tm_sec)
            output_msg += "\t-\t"
            if sensor.state == 1:
                output_msg += "triggered"
            else:
                output_msg += "normal"
            output_msg += "\t-\t"
            output_msg += sensor.description
            output_msg += "\n"

    return output_msg


@lib.event.subscribe('watchdog_tick')
def check_sensors(bot=None):
    """Checks if a sensor has changed its state."""

    global SENSORS
    global SENSORS_STATE
    global UPDATE_TICK_COUNTER

    if UPDATE_TICK_COUNTER >= (UPDATE_TICK_COUNTER_THRESHOLD - 1):

        # check if a state of a sensor has changed
        for sensor in SENSORS:
            if sensor.sensor_id in SENSORS_STATE.keys():

                if SENSORS_STATE[sensor.sensor_id] == sensor.state:
                    continue
                else:
                    SENSORS_STATE[sensor.sensor_id] = sensor.state
                    if sensor.state == 1:
                        for channel in lib.irc._channels:
                            bot.send(lib.irc.say(channel,
                                sensor.description + " just triggered"))
                    else:
                        for channel in lib.irc._channels:
                            bot.send(lib.irc.say(channel,
                                sensor.description + " back to normal"))
            else:
                SENSORS_STATE[sensor.sensor_id] = sensor.state


@lib.event.subscribe('watchdog_tick')
def update_sensor_data(bot=None):
    """Updates local sensor information."""

    global SENSORS
    global UPDATE_TICK_COUNTER

    UPDATE_TICK_COUNTER += 1
    if UPDATE_TICK_COUNTER >= UPDATE_TICK_COUNTER_THRESHOLD:
        UPDATE_TICK_COUNTER = 0

        # get sensor data from database
        try:
            conn = MySQLdb.connect(host=settings.ALERTR_MYSQL_SERVER,
                port=settings.ALERTR_MYSQL_PORT,
                user=settings.ALERTR_MYSQL_USER,
                passwd=settings.ALERTR_MYSQL_PASSWORD,
                db=settings.ALERTR_MYSQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT "
                + "id, "
                + "description, "
                + "state, "
                + "lastStateUpdated "
                + "FROM sensors")
            result = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            logging.exception("Not able to get sensor data from database.")
            return

        # update and add all existing sensors
        for sensor_tuple in result:
            sensor_id = sensor_tuple[0]
            description = sensor_tuple[1]
            state = sensor_tuple[2]
            last_state_updated = sensor_tuple[3]

            found = False
            for sensor in SENSORS:
                if sensor.sensor_id == sensor_id:
                    sensor.description = description
                    sensor.state = state
                    sensor.last_state_updated = last_state_updated
                    sensor.checked = True
                    found = True
                    break
            if not found:
                sensor = Sensor()
                sensor.sensor_id = sensor_id
                sensor.description = description
                sensor.state = state
                sensor.last_state_updated = last_state_updated
                sensor.checked = True
                SENSORS.append(sensor)

        # remove all sensors that do not exist any more
        for sensor in list(SENSORS):
            if not sensor.checked:
                SENSORS.remove(sensor)