from enum import Enum


class Zone(Enum):
    """Placeholder enum for zone identifiers (names or numeric IDs)."""

    L10_ALL_E = "L10_all_e"
    L11_ALL_E = "L11_all_e"
    L13_S_N = "L13_s_n"
    L14_S_N = "L14_s_n"
    L15_ALL_S = "L15_all_s"
    L16_ALL_S = "L16_all_s"
    L17_ALL_S = "L17_all_s"
    L18_W_ES = "L18_w_es"
    L19_W_E = "L19_w_e"
    L20_W_N = "L20_w_n"
    L21_NE_W = "L21_ne_w"
    L22_NE_W = "L22_ne_w"
    C4_S = "C4_s"
    C3_E = "C3_e"
    C1_N = "C1_n"
    C2_N = "C2_n"
    IS3_W = "IS3_w"
    SE4_S = "SE4_s"
    IS2_E = "IS2_e"
    IS1_N = "IS1_n"
    SE1_N = "SE1_n"
    SE2_N = "SE2_n"
    SE5_W = "SE5_w"
    SE6_W = "SE6_w"
    L3_N_E = "L3_n_e"
    L2_N_S = "L2_n_s"
    L1_N_WS = "L1_n_ws"
    I = "I"
    BB1_N = "BB1_n"
    IS4_W = "IS4_w"
    L6_E_N = "L6_e_n"
    L7_E_W = "L7_e_w"
    L8_E_SW = "L8_e_sw"
    L9_E_S = "L9_e_s"
    L5_ALL_N = "L5_all_n"
    L12_S_E = "L12_s_e"
    C5_W = "C5_w"
    SE3_E = "SE3_e"
    L4_ALL_N = "L4_all_n"


class ObjectType(Enum):
    """Placeholder enum for object types (e.g. car, pedestrian)."""
    PERSON = "PERSON"
    TRUCK = "TRUCK"
    CAR = "CAR"
    TWO_WHEELER = "TWO-WHEELER"
    UNKNOWN = "UNKNOWN"


class BootstrapServer(Enum):
    """Placeholder enum for Kafka bootstrap servers (host:port entries)."""
    EDGE = "10.2.0.163:29092"
    LOCAL = "10.2.0.164:19092"


KAFKA_SCHEMA_REGISTRY_URL="http://127.0.0.1:8081"
