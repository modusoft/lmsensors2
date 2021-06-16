from .agent_based_api.v1 import *
import json
import enum


class SensorType(enum.Enum):
    TEMP = "temp"
    IN = "in"
    FAN = "fan"
    CPU = "cpu"
    POWER = "power"
    CURR = "curr"
    ENERGY = "energy"
    INTRUSION = "intrusion"
    HUMIDITY = "humidity"


class Sensor:
    name = None
    sensor_type = None
    value = None
    crit_value = None
    warn_value = None


class Chip:
    name = None
    adapter = None
    sensors = []


def str_to_float(str_val):
    try:
        return float(str_val)
    except ValueError as e:
        return None


def parse_lmsensors2(string_table):
    json_str = ""
    for line in string_table:
        for word in line:
            json_str += word
            json_str += " "
        json_str += "\n"

    sensors = json.loads(json_str)

    parsed_sensors = []

    for chip_name in sensors:
        parsed = Chip()
        parsed.adapter = sensors[chip_name]["Adapter"]
        parsed.sensors = []  # wtf, why is this needed

        for sensor_name in sensors[chip_name]:
            if sensor_name == "Adapter":
                continue
            sensor = Sensor()
            sensor.name = sensor_name
            for sensor_val_name in sensors[chip_name][sensor_name]:
                if sensor_val_name.endswith("_input"):
                    sensor.value = str_to_float(sensors[chip_name][sensor_name][sensor_val_name])
                    for stype in SensorType:
                        if sensor_val_name.startswith(stype.value):
                            sensor.sensor_type = stype

                if sensor_val_name.endswith("crit"):
                    sensor.crit_value = str_to_float(sensors[chip_name][sensor_name][sensor_val_name])

                if sensor_val_name.endswith("max"):
                    sensor.warn_value = str_to_float(sensors[chip_name][sensor_name][sensor_val_name])

            parsed.sensors.append(sensor)

        parsed_sensors.append(parsed)

    return parsed_sensors


def _discover_lmsensors2(section, sensor_type):
    for chip in section:
        for sensor in chip.sensors:
            if sensor.sensor_type != sensor_type:
                continue
            service_name = chip.adapter + " " + sensor.name
            yield Service(item=service_name)


def check_lmsensors2(item, section):
    for chip in section:
        for sensor in chip.sensors:
            service_name = chip.adapter + " " + sensor.name
            if service_name == item:
                if sensor.value != None:
                    yield Metric("value", sensor.value)
                    if sensor.crit_value == None and sensor.warn_value == None:
                        yield Result(state=State.OK, summary="Always Ok")
                    else:
                        if sensor.crit_value != None and sensor.value >= sensor.crit_value:
                            yield Result(state=State.CRIT, summary="Value >= " + str(sensor.crit_value))
                        elif sensor.warn_value != None and sensor.value >= sensor.warn_value:
                            yield Result(state=State.WARN, summary="Value >= " + str(sensor.warn_value))
                        else:
                            yield Result(state=State.OK, summary="Value is Ok")
                else:
                    yield Result(state=State.WARN, summary="No input delivered by sensors command")
                return


def check_lmsensors2_temp(item, params, section):
    for chip in section:
        for sensor in chip.sensors:
            service_name = chip.adapter + " " + sensor.name
            if service_name == item:
                if sensor.value != None:
                    levels_lower = None
                    levels_upper = None

                    if params != {}:
                        # rule exists
                        if "levels" in params:
                            levels_upper = params["levels"]
                        if "levels_lower" in params:
                            levels_lower = params["levels_lower"]
                    elif sensor.crit_value != None or sensor.warn_value != None:
                        # no rules set use values from lm-sensors output
                        if sensor.crit_value == None:
                            sensor.crit_value = sensor.warn_value
                        elif sensor.warn_value == None:
                            sensor.warn_value = sensor.crit_value

                        levels_upper = (sensor.warn_value, sensor.crit_value)
                    elif sensor.warn_value == None and sensor.crit_value == None:
                        yield Result(state=State.OK, summary="Always Ok")
                        yield Metric("temperature", sensor.value)
                        return

                    result, metric = check_levels(
                        sensor.value,
                        levels_lower=levels_lower,
                        levels_upper=levels_upper,
                        metric_name="temperature",
                    )

                    yield metric
                    yield result
                else:
                    yield Result(state=State.WARN, summary="No input delivered by sensors command")
                return


def discover_lmsensors2_temp(section):
    for service in _discover_lmsensors2(section, SensorType.TEMP):
        yield service


def discover_lmsensors2_fan(section):
    for service in _discover_lmsensors2(section, SensorType.FAN):
        yield service


register.check_plugin(
    name="lmsensors2_temp",
    service_name="lmsensors2_temp %s",
    sections=["lmsensors2"],
    discovery_function=discover_lmsensors2_temp,
    check_function=check_lmsensors2_temp,
    check_ruleset_name="temperature",
    check_default_parameters={},
)

register.check_plugin(
    name="lmsensors2_fan",
    service_name="lmsensors2_fan %s",
    sections=["lmsensors2"],
    discovery_function=discover_lmsensors2_fan,
    check_function=check_lmsensors2,
)

register.agent_section(
    name="lmsensors2",
    parse_function=parse_lmsensors2,
)
