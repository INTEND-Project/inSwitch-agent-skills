---
name: city-weather
description: Get current weather for a named city by geocoding it to coordinates and calling a free REST weather API (Open-Meteo). Use when the user asks for the weather in a city/town or needs current conditions by place name.
---

# City Weather

## Goal

Get current weather for a city using a free REST API, returning a short human-readable summary with key metrics.

## Inputs

Collect:
- City name (optionally include country/region to disambiguate).
- Units preference (optional): `temperature_unit` = `celsius` or `fahrenheit`, `wind_speed_unit` = `kmh|ms|mph|kn`, `precipitation_unit` = `mm|inch`.

## Workflow (Open-Meteo)

1. Resolve the city name to coordinates with the Open-Meteo geocoding API.
   - Call:
     `https://geocoding-api.open-meteo.com/v1/search?name={CITY}&count=1&language=en&format=json`
   - Use the first result’s `latitude` and `longitude`.
   - If no results, ask for a more specific place name (add country/region).
2. Request current conditions from the Open-Meteo forecast API using coordinates.
   - Call:
     `https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m&timezone=auto`
   - Add unit parameters when provided: `temperature_unit`, `wind_speed_unit`, `precipitation_unit`.
3. Build the response from the `current` object in the API response.
   - Include: temperature, feels-like, humidity, precipitation, wind speed/direction, and a short condition label derived from `weather_code`.
   - If a condition label is needed, map `weather_code` using the WMO code table in the Open-Meteo docs.

## Output

Return a compact summary, for example:
- `{City}, {Country} — {Temp}°, feels like {Apparent}°. {Condition}. Humidity {RH}%. Wind {Speed} {Dir}. Precip {Precip}.`

## Error Handling

Handle common failures:
- Geocoding returns no results: ask for more specific location details.
- API HTTP 400 or missing fields: surface a brief error and retry with corrected parameters.

## Notes on Free Usage

Use the free Open-Meteo API for non-commercial use. For commercial use, use the customer API domain with an API key.

## Example (cURL)

```bash
curl "https://geocoding-api.open-meteo.com/v1/search?name=Seattle&count=1&language=en&format=json"
curl "https://api.open-meteo.com/v1/forecast?latitude=47.6062&longitude=-122.3321&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m&timezone=auto"
```
