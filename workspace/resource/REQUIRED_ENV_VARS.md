# Required Environment Variables by Service

## crosswalk_safety_alert
**Required:**
- **CROSSWALK_ZONE**: ID or name of the target crosswalk zone. Can be numeric (e.g., '5') or a string (e.g., 'C5_main'). If numeric, it will be automatically converted to the zone ID in the engine.
- **APPROACH_ZONES**: Comma-separated list of zone names or zone ids before the crosswalk zone. These zones are monitored for vehicle approach.
- **KAFKA_SOURCE_OBJECT_SPEEDS_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object speeds topic in the format `host:port`. This is the server from which the service will consume speed messages.
- **KAFKA_SOURCE_OBJECT_IN_ZONE_DETECTION_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object-in-zone detection topic in the format `host:port`. This is the server from which the service will consume detection messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

## flow_alert
**Required:**
- **KAFKA_SOURCE_OBJECT_COUNTING_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object counting topic in the format `host:port`. This is the server from which the service will consume counting messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **ZONES_OF_INTEREST**: List of zone names to keep. If empty, all zones are processed.
- **OBJECT_TYPE_FILTER**: List of object types/classes to keep (e.g., CAR, PEDESTRIAN). If empty, all types are processed.

## lidar_osef_data_streamer
**Required:**
- **OSEF_SOURCE**: Path to osef file or TCP stream. For TCP streams, use the format `tcp://hostname:port`.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Kafka bootstrap server in the format `host:port`.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

## object_counting
**Required:**
- **KAFKA_SOURCE_OBJECT_IN_ZONE_DETECTION_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object-in-zone detection topic in the format `host:port`. This is the server from which the service will consume detection messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **ZONES_OF_INTEREST**: List of zone names to keep. If empty, all zones are processed.
- **OBJECT_TYPE_FILTER**: List of object types/classes to keep (e.g., CAR, PEDESTRIAN). If empty, all types are processed.

## object_in_zone_detection
**Required:**
- **KAFKA_SOURCE_ZONES_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for zones topic in the format `host:port`. This is the server from which the service will consume messages.
- **KAFKA_SOURCE_OBJECTS_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for objects topic in the format `host:port`. This is the server from which the service will consume messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **OBJECT_TYPE_FILTER**: List of object class names or IDs (as strings) to keep. Numeric entries are treated as class IDs; non-numeric entries are treated as class names. If empty, all object types are processed.
- **ZONES_OF_INTEREST**: List of zone names or IDs (as strings) to keep. Numeric entries are treated as zone IDs; non-numeric entries as zone names. If empty, all zones are processed.

## object_speeds
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server in the format `host:port`. This is the server from which the service will consume messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **OBJECT_TYPE_FILTER**: List of object class names or IDs (as strings) to keep. Numeric entries are treated as class IDs; non-numeric entries are treated as class names. If empty, all object types are processed.

## osef_augmented_cloud
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server in the format `host:port`. This is the server from which the service will consume messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

## osef_scan_frame
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server in the format `host:port`. This is the server from which the service will consume messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

## osef_tracked_objects
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server in the format `host:port`. This is the server from which the service will consume messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

## osef_zones
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server in the format `host:port`. This is the server from which the service will consume messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

## overspeed_alert
**Required:**
- **KAFKA_SOURCE_OBJECT_SPEEDS_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object speeds topic in the format `host:port`. This is the server from which the service will consume speed messages.
- **KAFKA_SOURCE_OSEF_ZONES_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for OSEF zones topic in the format `host:port`. This is the server from which the service will consume zone messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **ZONES_OF_INTEREST**: List of zone names or IDs (as strings) for which to generate mock alerts. Numeric entries are treated as zone IDs; non-numeric entries as zone names. If empty, defaults to ['zone_1'] for mock data generation.

## traffic_jam_alert
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for traffic jam detection topic in the format `host:port`. This is the server from which the service will consume detection messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **ZONES_OF_INTEREST**: List of zone IDs or zone names to monitor. Numeric entries are treated as IDs; non-numeric entries as names. If empty, all zones will be monitored.

## traffic_jam_detector
**Required:**
- **KAFKA_SOURCE_OBJECT_SPEEDS_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object speeds topic in the format `host:port`. This is the server from which the service will consume speed messages.
- **KAFKA_SOURCE_OBJECT_IN_ZONE_DETECTION_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object-in-zone detection topic in the format `host:port`. This is the server from which the service will consume detection messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **ZONES_OF_INTEREST**: List of zone names or IDs (as strings) for which to generate mock alerts. Numeric entries are treated as zone IDs; non-numeric entries as zone names. If empty, defaults to ['zone_1'] for mock data generation.

## underspeed_alert
**Required:**
- **KAFKA_SOURCE_OBJECT_SPEEDS_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object speeds topic in the format `host:port`. This is the server from which the service will consume speed messages.
- **KAFKA_SOURCE_OSEF_ZONES_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for OSEF zones topic in the format `host:port`. This is the server from which the service will consume zone messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **ZONES_OF_INTEREST**: List of zone names or zone IDs (as strings) for which to generate mock alerts. Numeric entries are treated as IDs; non-numeric entries as names. If empty, defaults to ['zone_1'] for mock data generation.

## zones_passing
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for object-in-zone detection topic in the format `host:port`. This is the server from which the service will consume detection messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **FROM_ZONE**: Filter for the origin zone. If specified, only track transitions FROM this zone. Can be combined with TO_ZONE for exact transition tracking. If both are None, default zone transitions will be generated.
- **TO_ZONE**: Filter for the destination zone. If specified, only track transitions TO this zone. Can be combined with FROM_ZONE for exact transition tracking. If both are None, default zone transitions will be generated.
- **OBJECT_TYPE_FILTER**: List of object types/classes to track (e.g., CAR, PEDESTRIAN). If empty, all types are processed.

## zones_passing_alert
**Required:**
- **KAFKA_SOURCE_BOOTSTRAP_SERVER**: Source Kafka bootstrap server for zones passing topic in the format `host:port`. This is the server from which the service will consume zone passing messages.
- **KAFKA_DEST_BOOTSTRAP_SERVER**: Destination Kafka bootstrap server in the format `host:port`. This is the server to which the service will produce messages.
- **KAFKA_SCHEMA_REGISTRY_URL**: URL of the Schema Registry for Kafka.

**Optional (Filtration):**
- **FROM_ZONE**: Filter for the origin zone that triggers alerts. If specified, only alert on transitions FROM this zone. Can be combined with TO_ZONE for exact transition monitoring. If both are None, default alert transitions will be generated.
- **TO_ZONE**: Filter for the destination zone that triggers alerts. If specified, only alert on transitions TO this zone. Can be combined with FROM_ZONE for exact transition monitoring. If both are None, default alert transitions will be generated.
- **OBJECT_TYPE_FILTER**: List of object types/classes to alert on (e.g., CAR, PEDESTRIAN). If empty, all types are monitored.
