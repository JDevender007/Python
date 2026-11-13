"""
Weather API Client - Data Models
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Coordinates:
    """Geographic coordinates."""
    lat: float
    lon: float


@dataclass
class WeatherCondition:
    """Weather condition details."""
    id: int
    main: str
    description: str
    icon: str


@dataclass
class MainWeather:
    """Main weather metrics."""
    temp: float
    feels_like: float
    temp_min: float
    temp_max: float
    pressure: int
    humidity: int
    sea_level: Optional[int] = None
    grnd_level: Optional[int] = None


@dataclass
class Wind:
    """Wind information."""
    speed: float
    deg: int
    gust: Optional[float] = None


@dataclass
class Clouds:
    """Cloud coverage."""
    all: int


@dataclass
class Sys:
    """System information."""
    country: str
    sunrise: int
    sunset: int
    type: Optional[int] = None
    id: Optional[int] = None


@dataclass
class CurrentWeather:
    """Current weather data."""
    coord: Coordinates
    weather: List[WeatherCondition]
    base: str
    main: MainWeather
    visibility: int
    wind: Wind
    clouds: Clouds
    dt: int
    sys: Sys
    timezone: int
    id: int
    name: str
    cod: int

    @property
    def primary_condition(self) -> WeatherCondition:
        return self.weather[0] if self.weather else None

    @property
    def condition_description(self) -> str:
        return self.primary_condition.description.capitalize() if self.primary_condition else "Unknown"


@dataclass
class ForecastItem:
    """Single forecast item."""
    dt: int
    main: MainWeather
    weather: List[WeatherCondition]
    clouds: Clouds
    wind: Wind
    visibility: int
    pop: float
    sys: Sys
    dt_txt: str

    @property
    def primary_condition(self) -> WeatherCondition:
        return self.weather[0] if self.weather else None

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.dt)


@dataclass
class ForecastData:
    """Forecast response data."""
    cod: str
    message: int
    cnt: int
    list: List[ForecastItem]
    city: dict


@dataclass
class GeocodingResult:
    """Geocoding API result."""
    name: str
    local_names: Optional[dict] = None
    lat: float = 0.0
    lon: float = 0.0
    country: str = ""
    state: str = ""

    @property
    def display_name(self) -> str:
        parts = [self.name]
        if self.state:
            parts.append(self.state)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass
class CitySearchResult:
    """City search result for UI."""
    name: str
    country: str
    state: str
    lat: float
    lon: float

    @property
    def display(self) -> str:
        parts = [self.name]
        if self.state:
            parts.append(self.state)
        parts.append(self.country)
        return ", ".join(parts)


def parse_current_weather(data: dict) -> Optional[CurrentWeather]:
    """Parse current weather from API response."""
    try:
        coord = Coordinates(
            lat=data["coord"]["lat"],
            lon=data["coord"]["lon"]
        )

        weather = [
            WeatherCondition(
                id=w["id"],
                main=w["main"],
                description=w["description"],
                icon=w["icon"]
            ) for w in data["weather"]
        ]

        main = MainWeather(
            temp=data["main"]["temp"],
            feels_like=data["main"]["feels_like"],
            temp_min=data["main"]["temp_min"],
            temp_max=data["main"]["temp_max"],
            pressure=data["main"]["pressure"],
            humidity=data["main"]["humidity"],
            sea_level=data["main"].get("sea_level"),
            grnd_level=data["main"].get("grnd_level")
        )

        wind = Wind(
            speed=data["wind"]["speed"],
            deg=data["wind"]["deg"],
            gust=data["wind"].get("gust")
        )

        clouds = Clouds(all=data["clouds"]["all"])

        sys = Sys(
            country=data["sys"]["country"],
            sunrise=data["sys"]["sunrise"],
            sunset=data["sys"]["sunset"],
            type=data["sys"].get("type"),
            id=data["sys"].get("id")
        )

        return CurrentWeather(
            coord=coord,
            weather=weather,
            base=data["base"],
            main=main,
            visibility=data["visibility"],
            wind=wind,
            clouds=clouds,
            dt=data["dt"],
            sys=sys,
            timezone=data["timezone"],
            id=data["id"],
            name=data["name"],
            cod=data["cod"]
        )
    except (KeyError, TypeError) as e:
        return None


def parse_forecast(data: dict) -> Optional[ForecastData]:
    """Parse forecast from API response."""
    try:
        forecast_list = []
        for item in data["list"]:
            main = MainWeather(
                temp=item["main"]["temp"],
                feels_like=item["main"]["feels_like"],
                temp_min=item["main"]["temp_min"],
                temp_max=item["main"]["temp_max"],
                pressure=item["main"]["pressure"],
                humidity=item["main"]["humidity"]
            )

            weather = [
                WeatherCondition(
                    id=w["id"],
                    main=w["main"],
                    description=w["description"],
                    icon=w["icon"]
                ) for w in item["weather"]
            ]

            clouds = Clouds(all=item["clouds"]["all"])

            wind = Wind(
                speed=item["wind"]["speed"],
                deg=item["wind"]["deg"],
                gust=item["wind"].get("gust")
            )

            sys = Sys(
                country="",  # Not in forecast items
                sunrise=0,
                sunset=0
            )

            forecast_list.append(ForecastItem(
                dt=item["dt"],
                main=main,
                weather=weather,
                clouds=clouds,
                wind=wind,
                visibility=item.get("visibility", 10000),
                pop=item.get("pop", 0),
                sys=sys,
                dt_txt=item["dt_txt"]
            ))

        return ForecastData(
            cod=data["cod"],
            message=data["message"],
            cnt=data["cnt"],
            list=forecast_list,
            city=data["city"]
        )
    except (KeyError, TypeError) as e:
        return None


def parse_geocoding(data: list) -> List[GeocodingResult]:
    """Parse geocoding results."""
    results = []
    for item in data:
        results.append(GeocodingResult(
            name=item.get("name", ""),
            local_names=item.get("local_names"),
            lat=item.get("lat", 0),
            lon=item.get("lon", 0),
            country=item.get("country", ""),
            state=item.get("state", "")
        ))
    return results