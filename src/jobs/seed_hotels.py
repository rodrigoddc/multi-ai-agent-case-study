import asyncio
import logging
import os
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


RANDOM_SEED = 42
START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)
HOTEL_OPEN_DATE = date(2016, 1, 1)


BRANDS = [
    ("Aurora Hotels", "Luxury", "France", "Paris", 0.18),
    ("Seaway Hospitality", "Upscale", "Portugal", "Lisbon", 0.15),
    ("Summit Stays", "Luxury Resort", "Switzerland", "Zurich", 0.22),
    ("Metro Lodging", "Upper Midscale", "Germany", "Berlin", 0.12),
    ("Coastline Collection", "Resort", "Spain", "Barcelona", 0.17),
    ("Heritage Hospitality", "Boutique", "Austria", "Vienna", 0.14),
    ("Capital Suites", "Business Luxury", "Netherlands", "Amsterdam", 0.20),
    ("Greenstay Resorts", "Eco Boutique", "Czechia", "Prague", 0.10),
    ("Luxe Boutique", "Boutique Luxury", "Ireland", "Dublin", 0.16),
    ("Nordic Hotels", "Lifestyle", "Denmark", "Copenhagen", 0.19),
]

REGIONS = [
    ("Paris", "France", "Western Europe", "EUR", 48.8566, 2.3522, "Urban", 1.18),
    ("Lisbon", "Portugal", "Southern Europe", "EUR", 38.7223, -9.1393, "Coastal", 1.04),
    ("Zurich", "Switzerland", "Central Europe", "CHF", 47.3769, 8.5417, "Urban", 1.36),
    ("Berlin", "Germany", "Central Europe", "EUR", 52.52, 13.405, "Urban", 0.98),
    ("Barcelona", "Spain", "Southern Europe", "EUR", 41.3874, 2.1686, "Coastal", 1.15),
    ("Vienna", "Austria", "Central Europe", "EUR", 48.2082, 16.3738, "Urban", 1.03),
    (
        "Amsterdam",
        "Netherlands",
        "Western Europe",
        "EUR",
        52.3676,
        4.9041,
        "Urban",
        1.24,
    ),
    ("Prague", "Czechia", "Central Europe", "CZK", 50.0755, 14.4378, "Urban", 0.82),
    ("Dublin", "Ireland", "Western Europe", "EUR", 53.3498, -6.2603, "Urban", 1.16),
    (
        "Copenhagen",
        "Denmark",
        "Nordic Europe",
        "DKK",
        55.6761,
        12.5683,
        "Waterfront",
        1.22,
    ),
]

HOTELS = [
    ("City Center Grand", "Aurora Hotels", "Paris", 212, 5, "Luxury", 210.0, "rising"),
    (
        "Harbor View Suites",
        "Seaway Hospitality",
        "Lisbon",
        178,
        4,
        "Upscale",
        165.0,
        "stable",
    ),
    (
        "Alpine Retreat",
        "Summit Stays",
        "Zurich",
        96,
        5,
        "Luxury Resort",
        250.0,
        "rising",
    ),
    (
        "Urban Luxe Hotel",
        "Metro Lodging",
        "Berlin",
        250,
        4,
        "Upper Midscale",
        150.0,
        "softening",
    ),
    (
        "Mediterranean Bay",
        "Coastline Collection",
        "Barcelona",
        180,
        4,
        "Resort",
        175.0,
        "rising",
    ),
    (
        "Riverside Inn",
        "Heritage Hospitality",
        "Vienna",
        134,
        4,
        "Boutique",
        145.0,
        "stable",
    ),
    (
        "Skyline Plaza",
        "Capital Suites",
        "Amsterdam",
        220,
        5,
        "Business Luxury",
        205.0,
        "strong",
    ),
    (
        "Garden Escape",
        "Greenstay Resorts",
        "Prague",
        150,
        4,
        "Eco Boutique",
        130.0,
        "softening",
    ),
    (
        "Boutique East",
        "Luxe Boutique",
        "Dublin",
        84,
        5,
        "Boutique Luxury",
        190.0,
        "rising",
    ),
    (
        "Lakefront Hotel",
        "Nordic Hotels",
        "Copenhagen",
        140,
        4,
        "Lifestyle",
        195.0,
        "stable",
    ),
    (
        "Opera House Suites",
        "Heritage Hospitality",
        "Vienna",
        118,
        5,
        "Luxury",
        215.0,
        "strong",
    ),
    (
        "Marina Azul",
        "Coastline Collection",
        "Barcelona",
        205,
        4,
        "Resort",
        168.0,
        "stable",
    ),
    (
        "Canal District Hotel",
        "Capital Suites",
        "Amsterdam",
        160,
        4,
        "Business",
        182.0,
        "rising",
    ),
    (
        "Old Town Residence",
        "Greenstay Resorts",
        "Prague",
        112,
        3,
        "Boutique",
        108.0,
        "turnaround",
    ),
    (
        "Atlantic Conference Hotel",
        "Seaway Hospitality",
        "Lisbon",
        260,
        4,
        "Convention",
        155.0,
        "stable",
    ),
]

ROOM_TYPES = [
    ("Standard", 0.58, 1.00, 2),
    ("Superior", 0.22, 1.22, 2),
    ("Deluxe", 0.12, 1.48, 3),
    ("Junior Suite", 0.05, 1.95, 4),
    ("Executive Suite", 0.025, 2.55, 4),
    ("Presidential Suite", 0.005, 4.50, 6),
]

GUEST_SEGMENTS = [
    ("Business transient", 0.31, 2.1, 0.11),
    ("Leisure couple", 0.25, 3.2, 0.09),
    ("Family leisure", 0.16, 4.4, 0.13),
    ("Group tour", 0.09, 2.7, 0.18),
    ("Corporate negotiated", 0.12, 2.4, 0.22),
    ("Conference delegate", 0.07, 2.0, 0.15),
]

CHANNELS = [
    ("Direct web", "Direct", 0.25, 0.02),
    ("Mobile app", "Direct", 0.11, 0.01),
    ("Corporate booking tool", "Corporate", 0.12, 0.03),
    ("GDS", "Corporate", 0.07, 0.08),
    ("Booking.com", "OTA", 0.20, 0.17),
    ("Expedia", "OTA", 0.14, 0.16),
    ("Wholesaler", "Wholesale", 0.06, 0.21),
    ("Walk-in", "Property", 0.05, 0.00),
]

AMENITIES = [
    ("Restaurant", "Food & Beverage"),
    ("Rooftop bar", "Food & Beverage"),
    ("Spa", "Wellness"),
    ("Fitness center", "Wellness"),
    ("Conference rooms", "Meetings"),
    ("Coworking lounge", "Business"),
    ("Airport shuttle", "Transport"),
    ("EV charging", "Sustainability"),
    ("Pet friendly", "Guest Services"),
    ("Pool", "Wellness"),
]

PROMOTIONS = [
    ("Early Booker", "Advance purchase discount", 0.12),
    ("Stay 3 Pay 2", "Length of stay package", 0.18),
    ("Corporate Value", "Corporate negotiated tactical discount", 0.10),
    ("Weekend Escape", "Weekend leisure package", 0.15),
    ("Spa Credit", "Ancillary credit bundle", 0.08),
    ("None", "No promotion", 0.00),
]

REVIEW_TOPICS = [
    "cleanliness",
    "service",
    "breakfast",
    "location",
    "value",
    "wifi",
    "room comfort",
    "check-in",
    "food and beverage",
    "meeting facilities",
]

COMPETITORS = [
    "GlobalStay",
    "Premier Palace",
    "CityHub",
    "Traveler Inn",
    "Elite Collection",
]


def get_database_url() -> str:
    """Build database URL from the runtime environment."""
    postgres_user = os.environ["POSTGRES_USER"]
    postgres_password = os.environ["POSTGRES_PASSWORD"]
    postgres_db = os.environ["POSTGRES_DB"]
    db_host = os.getenv("DB_HOST", "pgbouncer")
    db_port = os.getenv("DB_PORT", "5432")
    database_url = os.getenv(
        "DATABASE_URL",
        f"postgresql+psycopg://{postgres_user}:{postgres_password}@{db_host}:{db_port}/{postgres_db}",
    )
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def money(value: float) -> Decimal:
    """Return a money-safe decimal rounded to two places."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pct(value: float) -> Decimal:
    """Return a percentage decimal rounded to two places."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def daterange(start: date, end: date):
    """Yield every date in the inclusive date range."""
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def weighted_choice(items: list[tuple[str, float]]) -> str:
    """Return one item name using configured weights."""
    total = sum(weight for _, weight in items)
    threshold = random.random() * total
    cumulative = 0.0
    for name, weight in items:
        cumulative += weight
        if cumulative >= threshold:
            return name
    return items[-1][0]


def seasonal_multiplier(day: date, region_type: str) -> float:
    """Return realistic seasonal demand pressure for a date and market type."""
    month = day.month
    if region_type == "Coastal":
        base = {
            1: 0.72,
            2: 0.74,
            3: 0.86,
            4: 1.00,
            5: 1.13,
            6: 1.28,
            7: 1.44,
            8: 1.38,
            9: 1.18,
            10: 1.00,
            11: 0.82,
            12: 0.90,
        }[month]
    elif region_type == "Waterfront":
        base = {
            1: 0.80,
            2: 0.82,
            3: 0.92,
            4: 1.02,
            5: 1.14,
            6: 1.24,
            7: 1.32,
            8: 1.25,
            9: 1.12,
            10: 1.02,
            11: 0.90,
            12: 0.98,
        }[month]
    else:
        base = {
            1: 0.86,
            2: 0.90,
            3: 1.02,
            4: 1.10,
            5: 1.16,
            6: 1.08,
            7: 0.98,
            8: 0.92,
            9: 1.20,
            10: 1.18,
            11: 1.04,
            12: 0.96,
        }[month]
    if day.weekday() in {4, 5}:
        return base * 1.08
    if day.weekday() in {1, 2}:
        return base * 1.03
    return base


async def execute_many(conn, sql: str, rows: list[dict]) -> None:
    """Execute SQL when row batches are non-empty."""
    if rows:
        await conn.execute(text(sql), rows)


async def execute_script(conn, sql: str) -> None:
    """Execute semicolon-delimited SQL statements."""
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            await conn.execute(text(statement))


async def create_schema(conn) -> None:
    """Create the complete analytical hotel schema."""
    await conn.execute(
        text(
            """
            DROP TABLE IF EXISTS
                agg_seasonal_patterns,
                agg_channel_performance,
                agg_sentiment_trends,
                agg_regional_market_share,
                agg_monthly_brand_performance,
                agg_daily_hotel_kpis,
                operational_maintenance_logs,
                operational_staff_schedules,
                fact_competitor_rates,
                fact_guest_reviews,
                fact_revenue,
                fact_occupancy,
                fact_bookings,
                hotel_rate_history,
                hotel_history,
                guest_reviews,
                hotels,
                bridge_hotel_amenities,
                dim_corporate_accounts,
                dim_loyalty_members,
                dim_promotion,
                dim_amenity,
                dim_channel,
                dim_guest_segment,
                dim_room_type,
                dim_hotel,
                dim_brand,
                dim_region,
                dim_date
            CASCADE
            """
        )
    )
    await execute_script(
        conn,
        """
            CREATE TABLE dim_date (
                id INTEGER PRIMARY KEY,
                calendar_date DATE NOT NULL UNIQUE,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                month INTEGER NOT NULL,
                month_name VARCHAR(20) NOT NULL,
                week_of_year INTEGER NOT NULL,
                day_of_month INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                day_name VARCHAR(20) NOT NULL,
                is_weekend BOOLEAN NOT NULL,
                is_holiday BOOLEAN NOT NULL,
                season VARCHAR(20) NOT NULL
            );

            CREATE TABLE dim_region (
                id SERIAL PRIMARY KEY,
                city VARCHAR(100) NOT NULL UNIQUE,
                country VARCHAR(100) NOT NULL,
                market VARCHAR(100) NOT NULL,
                currency_code CHAR(3) NOT NULL,
                latitude NUMERIC(9,4) NOT NULL,
                longitude NUMERIC(9,4) NOT NULL,
                market_type VARCHAR(50) NOT NULL,
                market_rate_index NUMERIC(6,2) NOT NULL
            );

            CREATE TABLE dim_brand (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                segment VARCHAR(100) NOT NULL,
                headquarters_country VARCHAR(100) NOT NULL,
                headquarters_city VARCHAR(100) NOT NULL,
                loyalty_multiplier NUMERIC(5,2) NOT NULL
            );

            CREATE TABLE dim_hotel (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                brand_id INTEGER NOT NULL REFERENCES dim_brand(id),
                region_id INTEGER NOT NULL REFERENCES dim_region(id),
                property_type VARCHAR(100) NOT NULL,
                star_rating INTEGER NOT NULL,
                rooms INTEGER NOT NULL,
                base_adr NUMERIC(10,2) NOT NULL,
                opening_date DATE NOT NULL,
                status VARCHAR(50) NOT NULL,
                trend VARCHAR(100) NOT NULL
            );

            CREATE TABLE dim_room_type (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                inventory_share NUMERIC(5,3) NOT NULL,
                rate_multiplier NUMERIC(6,2) NOT NULL,
                max_occupancy INTEGER NOT NULL
            );

            CREATE TABLE dim_guest_segment (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                demand_share NUMERIC(5,3) NOT NULL,
                avg_length_of_stay NUMERIC(5,2) NOT NULL,
                discount_rate NUMERIC(5,3) NOT NULL
            );

            CREATE TABLE dim_channel (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                channel_type VARCHAR(50) NOT NULL,
                demand_share NUMERIC(5,3) NOT NULL,
                commission_rate NUMERIC(5,3) NOT NULL
            );

            CREATE TABLE dim_amenity (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                category VARCHAR(100) NOT NULL
            );

            CREATE TABLE dim_promotion (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description VARCHAR(255) NOT NULL,
                discount_rate NUMERIC(5,3) NOT NULL
            );

            CREATE TABLE dim_loyalty_members (
                id SERIAL PRIMARY KEY,
                member_number VARCHAR(40) NOT NULL UNIQUE,
                tier VARCHAR(40) NOT NULL,
                home_country VARCHAR(100) NOT NULL,
                enrolled_date DATE NOT NULL,
                lifetime_nights INTEGER NOT NULL,
                lifetime_value NUMERIC(12,2) NOT NULL
            );

            CREATE TABLE dim_corporate_accounts (
                id SERIAL PRIMARY KEY,
                account_name VARCHAR(150) NOT NULL UNIQUE,
                industry VARCHAR(100) NOT NULL,
                headquarters_city VARCHAR(100) NOT NULL,
                contracted_discount NUMERIC(5,3) NOT NULL,
                annual_room_night_commitment INTEGER NOT NULL
            );

            CREATE TABLE bridge_hotel_amenities (
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id) ON DELETE CASCADE,
                amenity_id INTEGER NOT NULL REFERENCES dim_amenity(id) ON DELETE CASCADE,
                quality_score NUMERIC(4,2) NOT NULL,
                PRIMARY KEY (hotel_id, amenity_id)
            );

            CREATE TABLE hotels (
                id INTEGER PRIMARY KEY REFERENCES dim_hotel(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL UNIQUE,
                brand VARCHAR(255) NOT NULL,
                region VARCHAR(100) NOT NULL,
                rooms INTEGER NOT NULL,
                occupancy_rate NUMERIC(5,2) NOT NULL,
                revpar NUMERIC(10,2) NOT NULL,
                avg_sentiment NUMERIC(5,2) NOT NULL,
                trend VARCHAR(100) NOT NULL
            );

            CREATE TABLE guest_reviews (
                id SERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
                score INTEGER NOT NULL,
                sentiment NUMERIC(5,2) NOT NULL,
                comment VARCHAR(500) NOT NULL
            );

            CREATE TABLE hotel_history (
                id SERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id) ON DELETE CASCADE,
                valid_from DATE NOT NULL,
                valid_to DATE,
                brand_id INTEGER NOT NULL REFERENCES dim_brand(id),
                rooms INTEGER NOT NULL,
                star_rating INTEGER NOT NULL,
                property_type VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL,
                change_reason VARCHAR(255) NOT NULL
            );

            CREATE TABLE hotel_rate_history (
                id SERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id) ON DELETE CASCADE,
                room_type_id INTEGER NOT NULL REFERENCES dim_room_type(id),
                valid_from DATE NOT NULL,
                valid_to DATE,
                rate_plan VARCHAR(100) NOT NULL,
                base_rate NUMERIC(10,2) NOT NULL,
                cancellation_policy VARCHAR(100) NOT NULL
            );

            CREATE TABLE fact_bookings (
                id BIGSERIAL PRIMARY KEY,
                booking_reference VARCHAR(40) NOT NULL UNIQUE,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                booking_date_id INTEGER NOT NULL REFERENCES dim_date(id),
                stay_date_id INTEGER NOT NULL REFERENCES dim_date(id),
                room_type_id INTEGER NOT NULL REFERENCES dim_room_type(id),
                guest_segment_id INTEGER NOT NULL REFERENCES dim_guest_segment(id),
                channel_id INTEGER NOT NULL REFERENCES dim_channel(id),
                promotion_id INTEGER NOT NULL REFERENCES dim_promotion(id),
                loyalty_member_id INTEGER REFERENCES dim_loyalty_members(id),
                corporate_account_id INTEGER REFERENCES dim_corporate_accounts(id),
                rooms_booked INTEGER NOT NULL,
                guests INTEGER NOT NULL,
                length_of_stay INTEGER NOT NULL,
                status VARCHAR(40) NOT NULL,
                adr NUMERIC(10,2) NOT NULL,
                gross_room_revenue NUMERIC(12,2) NOT NULL,
                discount_amount NUMERIC(12,2) NOT NULL,
                commission_amount NUMERIC(12,2) NOT NULL,
                net_room_revenue NUMERIC(12,2) NOT NULL
            );

            CREATE TABLE fact_occupancy (
                id BIGSERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                date_id INTEGER NOT NULL REFERENCES dim_date(id),
                rooms_available INTEGER NOT NULL,
                rooms_sold INTEGER NOT NULL,
                rooms_out_of_order INTEGER NOT NULL,
                occupancy_rate NUMERIC(5,2) NOT NULL,
                UNIQUE (hotel_id, date_id)
            );

            CREATE TABLE fact_revenue (
                id BIGSERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                date_id INTEGER NOT NULL REFERENCES dim_date(id),
                room_revenue NUMERIC(12,2) NOT NULL,
                food_beverage_revenue NUMERIC(12,2) NOT NULL,
                spa_revenue NUMERIC(12,2) NOT NULL,
                parking_revenue NUMERIC(12,2) NOT NULL,
                other_revenue NUMERIC(12,2) NOT NULL,
                total_revenue NUMERIC(12,2) NOT NULL,
                revpar NUMERIC(10,2) NOT NULL,
                adr NUMERIC(10,2) NOT NULL,
                UNIQUE (hotel_id, date_id)
            );

            CREATE TABLE fact_guest_reviews (
                id BIGSERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                date_id INTEGER NOT NULL REFERENCES dim_date(id),
                booking_id BIGINT REFERENCES fact_bookings(id),
                channel_id INTEGER NOT NULL REFERENCES dim_channel(id),
                score INTEGER NOT NULL,
                sentiment NUMERIC(5,2) NOT NULL,
                topic VARCHAR(100) NOT NULL,
                response_time_hours NUMERIC(8,2) NOT NULL,
                comment VARCHAR(500) NOT NULL
            );

            CREATE TABLE fact_competitor_rates (
                id BIGSERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                date_id INTEGER NOT NULL REFERENCES dim_date(id),
                competitor_name VARCHAR(150) NOT NULL,
                competitor_rate NUMERIC(10,2) NOT NULL,
                rate_position VARCHAR(50) NOT NULL,
                comp_set_rank INTEGER NOT NULL
            );

            CREATE TABLE operational_staff_schedules (
                id BIGSERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                date_id INTEGER NOT NULL REFERENCES dim_date(id),
                department VARCHAR(100) NOT NULL,
                scheduled_hours NUMERIC(8,2) NOT NULL,
                overtime_hours NUMERIC(8,2) NOT NULL,
                labor_cost NUMERIC(12,2) NOT NULL
            );

            CREATE TABLE operational_maintenance_logs (
                id BIGSERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                date_id INTEGER NOT NULL REFERENCES dim_date(id),
                asset_category VARCHAR(100) NOT NULL,
                priority VARCHAR(40) NOT NULL,
                status VARCHAR(40) NOT NULL,
                resolution_hours NUMERIC(8,2) NOT NULL,
                cost NUMERIC(10,2) NOT NULL
            );

            CREATE TABLE agg_daily_hotel_kpis (
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                date_id INTEGER NOT NULL REFERENCES dim_date(id),
                rooms_available INTEGER NOT NULL,
                rooms_sold INTEGER NOT NULL,
                occupancy_rate NUMERIC(5,2) NOT NULL,
                adr NUMERIC(10,2) NOT NULL,
                revpar NUMERIC(10,2) NOT NULL,
                total_revenue NUMERIC(12,2) NOT NULL,
                review_count INTEGER NOT NULL,
                avg_review_score NUMERIC(5,2),
                avg_sentiment NUMERIC(5,2),
                PRIMARY KEY (hotel_id, date_id)
            );

            CREATE TABLE agg_monthly_brand_performance (
                brand_id INTEGER NOT NULL REFERENCES dim_brand(id),
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                hotel_count INTEGER NOT NULL,
                room_nights_available INTEGER NOT NULL,
                room_nights_sold INTEGER NOT NULL,
                occupancy_rate NUMERIC(5,2) NOT NULL,
                total_revenue NUMERIC(14,2) NOT NULL,
                adr NUMERIC(10,2) NOT NULL,
                revpar NUMERIC(10,2) NOT NULL,
                avg_sentiment NUMERIC(5,2),
                PRIMARY KEY (brand_id, year, month)
            );

            CREATE TABLE agg_regional_market_share (
                region_id INTEGER NOT NULL REFERENCES dim_region(id),
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                brand_id INTEGER NOT NULL REFERENCES dim_brand(id),
                rooms_sold INTEGER NOT NULL,
                room_revenue NUMERIC(14,2) NOT NULL,
                market_share_rooms NUMERIC(6,2) NOT NULL,
                market_share_revenue NUMERIC(6,2) NOT NULL,
                PRIMARY KEY (region_id, year, month, brand_id)
            );

            CREATE TABLE agg_sentiment_trends (
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                topic VARCHAR(100) NOT NULL,
                review_count INTEGER NOT NULL,
                avg_score NUMERIC(5,2) NOT NULL,
                avg_sentiment NUMERIC(5,2) NOT NULL,
                detractor_count INTEGER NOT NULL,
                promoter_count INTEGER NOT NULL,
                PRIMARY KEY (hotel_id, year, month, topic)
            );

            CREATE TABLE agg_channel_performance (
                hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                channel_id INTEGER NOT NULL REFERENCES dim_channel(id),
                bookings INTEGER NOT NULL,
                room_nights INTEGER NOT NULL,
                gross_revenue NUMERIC(14,2) NOT NULL,
                commission_amount NUMERIC(14,2) NOT NULL,
                net_revenue NUMERIC(14,2) NOT NULL,
                cancellation_rate NUMERIC(5,2) NOT NULL,
                PRIMARY KEY (hotel_id, year, month, channel_id)
            );

            CREATE TABLE agg_seasonal_patterns (
                region_id INTEGER NOT NULL REFERENCES dim_region(id),
                month INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                avg_occupancy_rate NUMERIC(5,2) NOT NULL,
                avg_adr NUMERIC(10,2) NOT NULL,
                avg_revpar NUMERIC(10,2) NOT NULL,
                demand_index NUMERIC(6,2) NOT NULL,
                PRIMARY KEY (region_id, month, day_of_week)
            );
            """,
    )


async def seed_dimensions(conn) -> dict[str, dict[str, int]]:
    """Seed dimensions and return lookup ids."""
    date_rows = []
    for current in daterange(
        START_DATE - timedelta(days=365), END_DATE + timedelta(days=365)
    ):
        date_rows.append(
            {
                "id": int(current.strftime("%Y%m%d")),
                "calendar_date": current,
                "year": current.year,
                "quarter": ((current.month - 1) // 3) + 1,
                "month": current.month,
                "month_name": current.strftime("%B"),
                "week_of_year": int(current.strftime("%V")),
                "day_of_month": current.day,
                "day_of_week": current.isoweekday(),
                "day_name": current.strftime("%A"),
                "is_weekend": current.weekday() >= 5,
                "is_holiday": current.month == 12 and current.day in {24, 25, 31},
                "season": "Winter"
                if current.month in {12, 1, 2}
                else "Spring"
                if current.month in {3, 4, 5}
                else "Summer"
                if current.month in {6, 7, 8}
                else "Autumn",
            }
        )
    await execute_many(
        conn,
        """
        INSERT INTO dim_date (id, calendar_date, year, quarter, month, month_name,
            week_of_year, day_of_month, day_of_week, day_name, is_weekend, is_holiday, season)
        VALUES (:id, :calendar_date, :year, :quarter, :month, :month_name,
            :week_of_year, :day_of_month, :day_of_week, :day_name, :is_weekend, :is_holiday, :season)
        """,
        date_rows,
    )

    await execute_many(
        conn,
        """
        INSERT INTO dim_region (city, country, market, currency_code, latitude, longitude, market_type, market_rate_index)
        VALUES (:city, :country, :market, :currency_code, :latitude, :longitude, :market_type, :market_rate_index)
        """,
        [
            {
                "city": city,
                "country": country,
                "market": market,
                "currency_code": currency,
                "latitude": lat,
                "longitude": lon,
                "market_type": market_type,
                "market_rate_index": money(rate_index),
            }
            for city, country, market, currency, lat, lon, market_type, rate_index in REGIONS
        ],
    )
    await execute_many(
        conn,
        """
        INSERT INTO dim_brand (name, segment, headquarters_country, headquarters_city, loyalty_multiplier)
        VALUES (:name, :segment, :headquarters_country, :headquarters_city, :loyalty_multiplier)
        """,
        [
            {
                "name": name,
                "segment": segment,
                "headquarters_country": country,
                "headquarters_city": city,
                "loyalty_multiplier": money(multiplier),
            }
            for name, segment, country, city, multiplier in BRANDS
        ],
    )
    await execute_many(
        conn,
        """
        INSERT INTO dim_room_type (name, inventory_share, rate_multiplier, max_occupancy)
        VALUES (:name, :inventory_share, :rate_multiplier, :max_occupancy)
        """,
        [
            {
                "name": name,
                "inventory_share": Decimal(str(share)),
                "rate_multiplier": money(multiplier),
                "max_occupancy": max_occupancy,
            }
            for name, share, multiplier, max_occupancy in ROOM_TYPES
        ],
    )
    await execute_many(
        conn,
        """
        INSERT INTO dim_guest_segment (name, demand_share, avg_length_of_stay, discount_rate)
        VALUES (:name, :demand_share, :avg_length_of_stay, :discount_rate)
        """,
        [
            {
                "name": name,
                "demand_share": Decimal(str(share)),
                "avg_length_of_stay": money(los),
                "discount_rate": Decimal(str(discount)),
            }
            for name, share, los, discount in GUEST_SEGMENTS
        ],
    )
    await execute_many(
        conn,
        """
        INSERT INTO dim_channel (name, channel_type, demand_share, commission_rate)
        VALUES (:name, :channel_type, :demand_share, :commission_rate)
        """,
        [
            {
                "name": name,
                "channel_type": channel_type,
                "demand_share": Decimal(str(share)),
                "commission_rate": Decimal(str(commission)),
            }
            for name, channel_type, share, commission in CHANNELS
        ],
    )
    await execute_many(
        conn,
        """
        INSERT INTO dim_amenity (name, category) VALUES (:name, :category)
        """,
        [{"name": name, "category": category} for name, category in AMENITIES],
    )
    await execute_many(
        conn,
        """
        INSERT INTO dim_promotion (name, description, discount_rate)
        VALUES (:name, :description, :discount_rate)
        """,
        [
            {
                "name": name,
                "description": description,
                "discount_rate": Decimal(str(discount)),
            }
            for name, description, discount in PROMOTIONS
        ],
    )

    await conn.execute(
        text(
            """
            INSERT INTO dim_hotel (name, brand_id, region_id, property_type, star_rating, rooms, base_adr, opening_date, status, trend)
            SELECT :name, b.id, r.id, :property_type, :star_rating, :rooms, :base_adr, :opening_date, 'Open', :trend
            FROM dim_brand b CROSS JOIN dim_region r
            WHERE b.name = :brand_name AND r.city = :city
            """
        ),
        [
            {
                "name": name,
                "brand_name": brand,
                "city": city,
                "rooms": rooms,
                "star_rating": star_rating,
                "property_type": property_type,
                "base_adr": money(base_adr),
                "opening_date": HOTEL_OPEN_DATE
                + timedelta(days=random.randint(0, 2500)),
                "trend": trend,
            }
            for name, brand, city, rooms, star_rating, property_type, base_adr, trend in HOTELS
        ],
    )

    loyalty_rows = []
    countries = [region[1] for region in REGIONS]
    tiers = ["Member", "Silver", "Gold", "Platinum", "Diamond"]
    for idx in range(1, 501):
        tier = random.choices(tiers, weights=[45, 25, 17, 9, 4], k=1)[0]
        lifetime_nights = random.randint(1, 220) + tiers.index(tier) * 35
        loyalty_rows.append(
            {
                "member_number": f"LH{idx:07d}",
                "tier": tier,
                "home_country": random.choice(countries),
                "enrolled_date": START_DATE - timedelta(days=random.randint(60, 2500)),
                "lifetime_nights": lifetime_nights,
                "lifetime_value": money(lifetime_nights * random.uniform(120, 330)),
            }
        )
    await execute_many(
        conn,
        """
        INSERT INTO dim_loyalty_members (member_number, tier, home_country, enrolled_date, lifetime_nights, lifetime_value)
        VALUES (:member_number, :tier, :home_country, :enrolled_date, :lifetime_nights, :lifetime_value)
        """,
        loyalty_rows,
    )

    corporate_accounts = [
        ("Aster Consulting", "Consulting", "Paris", 0.16, 1400),
        ("Northwind Pharma", "Healthcare", "Zurich", 0.12, 900),
        ("Globex Energy", "Energy", "Berlin", 0.14, 1100),
        ("Initech Systems", "Technology", "Dublin", 0.18, 1700),
        ("Oceanic Airlines", "Travel", "Lisbon", 0.20, 2100),
        ("Umbrella Events", "Events", "Amsterdam", 0.11, 700),
    ]
    await execute_many(
        conn,
        """
        INSERT INTO dim_corporate_accounts (account_name, industry, headquarters_city, contracted_discount, annual_room_night_commitment)
        VALUES (:account_name, :industry, :headquarters_city, :contracted_discount, :annual_room_night_commitment)
        """,
        [
            {
                "account_name": name,
                "industry": industry,
                "headquarters_city": city,
                "contracted_discount": Decimal(str(discount)),
                "annual_room_night_commitment": commitment,
            }
            for name, industry, city, discount, commitment in corporate_accounts
        ],
    )

    lookup_queries = {
        "dim_brand": "SELECT id, name FROM dim_brand",
        "dim_region": "SELECT id, city AS name FROM dim_region",
        "dim_hotel": "SELECT id, name FROM dim_hotel",
        "dim_room_type": "SELECT id, name FROM dim_room_type",
        "dim_guest_segment": "SELECT id, name FROM dim_guest_segment",
        "dim_channel": "SELECT id, name FROM dim_channel",
        "dim_promotion": "SELECT id, name FROM dim_promotion",
        "dim_amenity": "SELECT id, name FROM dim_amenity",
        "dim_loyalty_members": "SELECT id, member_number AS name FROM dim_loyalty_members",
        "dim_corporate_accounts": "SELECT id, account_name AS name FROM dim_corporate_accounts",
    }
    lookups = {}
    for table, query in lookup_queries.items():
        result = await conn.execute(text(query))
        lookups[table] = {row.name: row.id for row in result}
    return lookups


async def seed_hotels_and_scd(conn, lookups: dict[str, dict[str, int]]) -> None:
    """Seed hotel compatibility and historical tables."""
    hotel_rows = []
    history_rows = []
    rate_rows = []
    amenity_rows = []
    for name, brand, city, rooms, star_rating, property_type, base_adr, trend in HOTELS:
        hotel_id = lookups["dim_hotel"][name]
        hotel_rows.append(
            {
                "id": hotel_id,
                "name": name,
                "brand": brand,
                "region": city,
                "rooms": rooms,
                "occupancy_rate": pct(70.0),
                "revpar": money(base_adr * 0.70),
                "avg_sentiment": pct(78.0),
                "trend": trend,
            }
        )
        history_rows.extend(
            [
                {
                    "hotel_id": hotel_id,
                    "valid_from": HOTEL_OPEN_DATE,
                    "valid_to": date(2022, 12, 31),
                    "brand_id": lookups["dim_brand"][brand],
                    "rooms": max(50, int(rooms * random.uniform(0.82, 0.94))),
                    "star_rating": max(3, star_rating - random.choice([0, 1])),
                    "property_type": property_type,
                    "status": "Open",
                    "change_reason": "Initial property profile",
                },
                {
                    "hotel_id": hotel_id,
                    "valid_from": date(2023, 1, 1),
                    "valid_to": None,
                    "brand_id": lookups["dim_brand"][brand],
                    "rooms": rooms,
                    "star_rating": star_rating,
                    "property_type": property_type,
                    "status": "Open",
                    "change_reason": "Post-renovation inventory and rating refresh",
                },
            ]
        )
        for room_name, _, multiplier, _ in ROOM_TYPES:
            room_type_id = lookups["dim_room_type"][room_name]
            rate_rows.append(
                {
                    "hotel_id": hotel_id,
                    "room_type_id": room_type_id,
                    "valid_from": START_DATE - timedelta(days=365),
                    "valid_to": date(2024, 12, 31),
                    "rate_plan": "Best Flexible Rate",
                    "base_rate": money(base_adr * multiplier * 0.94),
                    "cancellation_policy": "Flexible until 18:00 arrival day",
                }
            )
            rate_rows.append(
                {
                    "hotel_id": hotel_id,
                    "room_type_id": room_type_id,
                    "valid_from": date(2025, 1, 1),
                    "valid_to": None,
                    "rate_plan": "Best Flexible Rate",
                    "base_rate": money(base_adr * multiplier * 1.04),
                    "cancellation_policy": "Flexible until 14:00 day before arrival",
                }
            )
        amenity_names = random.sample([a[0] for a in AMENITIES], k=random.randint(5, 9))
        for amenity_name in amenity_names:
            amenity_rows.append(
                {
                    "hotel_id": hotel_id,
                    "amenity_id": lookups["dim_amenity"][amenity_name],
                    "quality_score": money(random.uniform(3.55, 4.95)),
                }
            )
    await execute_many(
        conn,
        """
        INSERT INTO hotels (id, name, brand, region, rooms, occupancy_rate, revpar, avg_sentiment, trend)
        VALUES (:id, :name, :brand, :region, :rooms, :occupancy_rate, :revpar, :avg_sentiment, :trend)
        """,
        hotel_rows,
    )
    await execute_many(
        conn,
        """
        INSERT INTO hotel_history (hotel_id, valid_from, valid_to, brand_id, rooms, star_rating, property_type, status, change_reason)
        VALUES (:hotel_id, :valid_from, :valid_to, :brand_id, :rooms, :star_rating, :property_type, :status, :change_reason)
        """,
        history_rows,
    )
    await execute_many(
        conn,
        """
        INSERT INTO hotel_rate_history (hotel_id, room_type_id, valid_from, valid_to, rate_plan, base_rate, cancellation_policy)
        VALUES (:hotel_id, :room_type_id, :valid_from, :valid_to, :rate_plan, :base_rate, :cancellation_policy)
        """,
        rate_rows,
    )
    await execute_many(
        conn,
        """
        INSERT INTO bridge_hotel_amenities (hotel_id, amenity_id, quality_score)
        VALUES (:hotel_id, :amenity_id, :quality_score)
        """,
        amenity_rows,
    )


async def seed_facts(conn, lookups: dict[str, dict[str, int]]) -> None:
    """Seed booking, occupancy, revenue, review, competitor, and operational facts."""
    hotels_result = await conn.execute(
        text(
            """
            SELECT h.id, h.name, h.rooms, h.base_adr, h.trend, r.market_type, r.market_rate_index
            FROM dim_hotel h
            JOIN dim_region r ON r.id = h.region_id
            ORDER BY h.id
            """
        )
    )
    hotels = hotels_result.mappings().all()
    loyalty_ids = list(lookups["dim_loyalty_members"].values())
    corporate_ids = list(lookups["dim_corporate_accounts"].values())

    segment_weights = [(name, share) for name, share, _, _ in GUEST_SEGMENTS]
    channel_weights = [(name, share) for name, _, share, _ in CHANNELS]
    room_weights = [(name, share) for name, share, _, _ in ROOM_TYPES]

    occupancy_rows = []
    revenue_rows = []
    competitor_rows = []
    staff_rows = []
    maintenance_rows = []
    booking_rows = []
    review_rows = []
    guest_review_rows = []
    booking_counter = 1

    channel_commission = {name: commission for name, _, _, commission in CHANNELS}
    segment_discount = {name: discount for name, _, _, discount in GUEST_SEGMENTS}
    segment_los = {name: los for name, _, los, _ in GUEST_SEGMENTS}
    promotion_discount = {name: discount for name, _, discount in PROMOTIONS}
    room_multiplier = {name: multiplier for name, _, multiplier, _ in ROOM_TYPES}

    for current in daterange(START_DATE, END_DATE):
        date_id = int(current.strftime("%Y%m%d"))
        for hotel in hotels:
            season = seasonal_multiplier(current, hotel["market_type"])
            trend_factor = {
                "strong": 1.12,
                "rising": 1.06,
                "stable": 1.00,
                "turnaround": 0.94,
                "softening": 0.90,
            }.get(hotel["trend"], 1.0)
            noise = random.uniform(0.88, 1.12)
            occupancy_rate = max(34.0, min(96.5, 68.0 * season * trend_factor * noise))
            rooms_out = random.randint(0, max(1, hotel["rooms"] // 80))
            rooms_available = hotel["rooms"] - rooms_out
            rooms_sold = min(
                rooms_available, int(rooms_available * occupancy_rate / 100)
            )
            adr = float(hotel["base_adr"]) * season * random.uniform(0.92, 1.16)
            room_revenue = adr * rooms_sold
            fb_revenue = room_revenue * random.uniform(0.16, 0.32)
            spa_revenue = room_revenue * random.uniform(0.02, 0.12)
            parking_revenue = room_revenue * random.uniform(0.01, 0.04)
            other_revenue = room_revenue * random.uniform(0.02, 0.08)
            total_revenue = (
                room_revenue
                + fb_revenue
                + spa_revenue
                + parking_revenue
                + other_revenue
            )
            revpar = room_revenue / rooms_available if rooms_available else 0.0

            occupancy_rows.append(
                {
                    "hotel_id": hotel["id"],
                    "date_id": date_id,
                    "rooms_available": rooms_available,
                    "rooms_sold": rooms_sold,
                    "rooms_out_of_order": rooms_out,
                    "occupancy_rate": pct(occupancy_rate),
                }
            )
            revenue_rows.append(
                {
                    "hotel_id": hotel["id"],
                    "date_id": date_id,
                    "room_revenue": money(room_revenue),
                    "food_beverage_revenue": money(fb_revenue),
                    "spa_revenue": money(spa_revenue),
                    "parking_revenue": money(parking_revenue),
                    "other_revenue": money(other_revenue),
                    "total_revenue": money(total_revenue),
                    "revpar": money(revpar),
                    "adr": money(adr),
                }
            )
            for competitor in COMPETITORS:
                competitor_rate = adr * random.uniform(0.82, 1.24)
                competitor_rows.append(
                    {
                        "hotel_id": hotel["id"],
                        "date_id": date_id,
                        "competitor_name": competitor,
                        "competitor_rate": money(competitor_rate),
                        "rate_position": "Above"
                        if adr > competitor_rate * 1.03
                        else "Below"
                        if adr < competitor_rate * 0.97
                        else "Parity",
                        "comp_set_rank": random.randint(1, 6),
                    }
                )
            for department, hours_per_room, hourly_cost in [
                ("Front Office", 0.45, 28),
                ("Housekeeping", 0.62, 23),
                ("Food & Beverage", 0.38, 25),
                ("Maintenance", 0.16, 31),
                ("Management", 0.12, 45),
            ]:
                scheduled_hours = max(
                    8, rooms_sold * hours_per_room + random.uniform(-4, 8)
                )
                overtime = max(
                    0, scheduled_hours - hotel["rooms"] * hours_per_room * 0.86
                ) * random.uniform(0.0, 0.18)
                staff_rows.append(
                    {
                        "hotel_id": hotel["id"],
                        "date_id": date_id,
                        "department": department,
                        "scheduled_hours": money(scheduled_hours),
                        "overtime_hours": money(overtime),
                        "labor_cost": money(
                            (scheduled_hours + overtime * 1.5) * hourly_cost
                        ),
                    }
                )
            if random.random() < 0.18:
                maintenance_rows.append(
                    {
                        "hotel_id": hotel["id"],
                        "date_id": date_id,
                        "asset_category": random.choice(
                            [
                                "Guest room",
                                "HVAC",
                                "Elevator",
                                "Kitchen",
                                "Pool",
                                "IT",
                                "Laundry",
                            ]
                        ),
                        "priority": random.choices(
                            ["Low", "Medium", "High", "Critical"],
                            weights=[45, 35, 16, 4],
                            k=1,
                        )[0],
                        "status": random.choices(
                            ["Resolved", "Open", "Deferred"], weights=[82, 13, 5], k=1
                        )[0],
                        "resolution_hours": money(random.uniform(1.0, 72.0)),
                        "cost": money(random.uniform(45, 4500)),
                    }
                )

            target_booking_rooms = rooms_sold
            while target_booking_rooms > 0:
                rooms_booked = min(
                    target_booking_rooms,
                    random.choices(
                        [1, 2, 3, 4, 8, 12], weights=[68, 18, 6, 4, 3, 1], k=1
                    )[0],
                )
                segment_name = weighted_choice(segment_weights)
                channel_name = weighted_choice(channel_weights)
                room_name = weighted_choice(room_weights)
                promotion_name = random.choices(
                    [name for name, _, _ in PROMOTIONS],
                    weights=[12, 8, 10, 9, 6, 55],
                    k=1,
                )[0]
                los = max(1, int(random.gauss(segment_los[segment_name], 0.9)))
                booking_lead = random.randint(0, 90)
                booking_date = current - timedelta(days=booking_lead)
                gross_adr = adr * room_multiplier[room_name]
                total_discount_rate = (
                    segment_discount[segment_name] + promotion_discount[promotion_name]
                )
                discount = gross_adr * rooms_booked * total_discount_rate
                gross = gross_adr * rooms_booked * los
                commission = gross * channel_commission[channel_name]
                net = gross - discount - commission
                is_corporate = segment_name in {
                    "Corporate negotiated",
                    "Conference delegate",
                }
                booking_rows.append(
                    {
                        "booking_reference": f"BK{booking_counter:010d}",
                        "hotel_id": hotel["id"],
                        "booking_date_id": int(booking_date.strftime("%Y%m%d")),
                        "stay_date_id": date_id,
                        "room_type_id": lookups["dim_room_type"][room_name],
                        "guest_segment_id": lookups["dim_guest_segment"][segment_name],
                        "channel_id": lookups["dim_channel"][channel_name],
                        "promotion_id": lookups["dim_promotion"][promotion_name],
                        "loyalty_member_id": random.choice(loyalty_ids)
                        if random.random() < 0.33
                        else None,
                        "corporate_account_id": random.choice(corporate_ids)
                        if is_corporate and random.random() < 0.62
                        else None,
                        "rooms_booked": rooms_booked,
                        "guests": rooms_booked * random.randint(1, 3),
                        "length_of_stay": los,
                        "status": random.choices(
                            ["Stayed", "Cancelled", "No-show"], weights=[91, 7, 2], k=1
                        )[0],
                        "adr": money(gross_adr),
                        "gross_room_revenue": money(gross),
                        "discount_amount": money(discount),
                        "commission_amount": money(commission),
                        "net_room_revenue": money(net),
                    }
                )
                if random.random() < 0.055:
                    base_sentiment = (
                        0.74 + (occupancy_rate - 70) / 350 + random.uniform(-0.18, 0.18)
                    )
                    sentiment = max(0.20, min(0.98, base_sentiment))
                    score = max(1, min(5, round(sentiment * 5)))
                    topic = random.choice(REVIEW_TOPICS)
                    comment = f"{topic.title()} experience at {hotel['name']} was {'excellent' if score >= 5 else 'good' if score >= 4 else 'mixed' if score == 3 else 'below expectations'}."
                    review_rows.append(
                        {
                            "hotel_id": hotel["id"],
                            "date_id": date_id,
                            "booking_reference": f"BK{booking_counter:010d}",
                            "channel_id": lookups["dim_channel"][channel_name],
                            "score": score,
                            "sentiment": pct(sentiment),
                            "topic": topic,
                            "response_time_hours": money(random.uniform(1, 96)),
                            "comment": comment,
                        }
                    )
                    guest_review_rows.append(
                        {
                            "hotel_id": hotel["id"],
                            "score": score,
                            "sentiment": pct(sentiment),
                            "comment": comment,
                        }
                    )
                target_booking_rooms -= rooms_booked
                booking_counter += 1

    for sql, rows in [
        (
            """
            INSERT INTO fact_occupancy (hotel_id, date_id, rooms_available, rooms_sold, rooms_out_of_order, occupancy_rate)
            VALUES (:hotel_id, :date_id, :rooms_available, :rooms_sold, :rooms_out_of_order, :occupancy_rate)
            """,
            occupancy_rows,
        ),
        (
            """
            INSERT INTO fact_revenue (hotel_id, date_id, room_revenue, food_beverage_revenue, spa_revenue, parking_revenue, other_revenue, total_revenue, revpar, adr)
            VALUES (:hotel_id, :date_id, :room_revenue, :food_beverage_revenue, :spa_revenue, :parking_revenue, :other_revenue, :total_revenue, :revpar, :adr)
            """,
            revenue_rows,
        ),
        (
            """
            INSERT INTO fact_competitor_rates (hotel_id, date_id, competitor_name, competitor_rate, rate_position, comp_set_rank)
            VALUES (:hotel_id, :date_id, :competitor_name, :competitor_rate, :rate_position, :comp_set_rank)
            """,
            competitor_rows,
        ),
        (
            """
            INSERT INTO operational_staff_schedules (hotel_id, date_id, department, scheduled_hours, overtime_hours, labor_cost)
            VALUES (:hotel_id, :date_id, :department, :scheduled_hours, :overtime_hours, :labor_cost)
            """,
            staff_rows,
        ),
        (
            """
            INSERT INTO operational_maintenance_logs (hotel_id, date_id, asset_category, priority, status, resolution_hours, cost)
            VALUES (:hotel_id, :date_id, :asset_category, :priority, :status, :resolution_hours, :cost)
            """,
            maintenance_rows,
        ),
        (
            """
            INSERT INTO fact_bookings (booking_reference, hotel_id, booking_date_id, stay_date_id, room_type_id, guest_segment_id, channel_id, promotion_id, loyalty_member_id, corporate_account_id, rooms_booked, guests, length_of_stay, status, adr, gross_room_revenue, discount_amount, commission_amount, net_room_revenue)
            VALUES (:booking_reference, :hotel_id, :booking_date_id, :stay_date_id, :room_type_id, :guest_segment_id, :channel_id, :promotion_id, :loyalty_member_id, :corporate_account_id, :rooms_booked, :guests, :length_of_stay, :status, :adr, :gross_room_revenue, :discount_amount, :commission_amount, :net_room_revenue)
            """,
            booking_rows,
        ),
        (
            """
            INSERT INTO guest_reviews (hotel_id, score, sentiment, comment)
            VALUES (:hotel_id, :score, :sentiment, :comment)
            """,
            guest_review_rows,
        ),
    ]:
        for offset in range(0, len(rows), 5000):
            await execute_many(conn, sql, rows[offset : offset + 5000])

    await execute_many(
        conn,
        """
        INSERT INTO fact_guest_reviews (hotel_id, date_id, booking_id, channel_id, score, sentiment, topic, response_time_hours, comment)
        SELECT :hotel_id, :date_id, b.id, :channel_id, :score, :sentiment, :topic, :response_time_hours, :comment
        FROM fact_bookings b
        WHERE b.booking_reference = :booking_reference
        """,
        review_rows,
    )


async def seed_aggregates(conn) -> None:
    """Populate summary tables for fast analytical queries."""
    await execute_script(
        conn,
        """
            INSERT INTO agg_daily_hotel_kpis
            SELECT
                o.hotel_id,
                o.date_id,
                o.rooms_available,
                o.rooms_sold,
                o.occupancy_rate,
                r.adr,
                r.revpar,
                r.total_revenue,
                COUNT(gr.id)::INTEGER AS review_count,
                AVG(gr.score)::NUMERIC(5,2) AS avg_review_score,
                AVG(gr.sentiment)::NUMERIC(5,2) AS avg_sentiment
            FROM fact_occupancy o
            JOIN fact_revenue r ON r.hotel_id = o.hotel_id AND r.date_id = o.date_id
            LEFT JOIN fact_guest_reviews gr ON gr.hotel_id = o.hotel_id AND gr.date_id = o.date_id
            GROUP BY o.hotel_id, o.date_id, o.rooms_available, o.rooms_sold, o.occupancy_rate, r.adr, r.revpar, r.total_revenue;

            INSERT INTO agg_monthly_brand_performance
            SELECT
                h.brand_id,
                d.year,
                d.month,
                COUNT(DISTINCT h.id)::INTEGER AS hotel_count,
                SUM(k.rooms_available)::INTEGER AS room_nights_available,
                SUM(k.rooms_sold)::INTEGER AS room_nights_sold,
                (SUM(k.rooms_sold)::NUMERIC / NULLIF(SUM(k.rooms_available), 0) * 100)::NUMERIC(5,2) AS occupancy_rate,
                SUM(k.total_revenue)::NUMERIC(14,2) AS total_revenue,
                (SUM(fr.room_revenue) / NULLIF(SUM(k.rooms_sold), 0))::NUMERIC(10,2) AS adr,
                (SUM(fr.room_revenue) / NULLIF(SUM(k.rooms_available), 0))::NUMERIC(10,2) AS revpar,
                AVG(k.avg_sentiment)::NUMERIC(5,2) AS avg_sentiment
            FROM agg_daily_hotel_kpis k
            JOIN dim_date d ON d.id = k.date_id
            JOIN dim_hotel h ON h.id = k.hotel_id
            JOIN fact_revenue fr ON fr.hotel_id = k.hotel_id AND fr.date_id = k.date_id
            GROUP BY h.brand_id, d.year, d.month;

            INSERT INTO agg_regional_market_share
            WITH brand_region AS (
                SELECT
                    h.region_id,
                    d.year,
                    d.month,
                    h.brand_id,
                    SUM(k.rooms_sold)::INTEGER AS rooms_sold,
                    SUM(fr.room_revenue)::NUMERIC(14,2) AS room_revenue
                FROM agg_daily_hotel_kpis k
                JOIN dim_date d ON d.id = k.date_id
                JOIN dim_hotel h ON h.id = k.hotel_id
                JOIN fact_revenue fr ON fr.hotel_id = k.hotel_id AND fr.date_id = k.date_id
                GROUP BY h.region_id, d.year, d.month, h.brand_id
            ), totals AS (
                SELECT region_id, year, month, SUM(rooms_sold) total_rooms, SUM(room_revenue) total_revenue
                FROM brand_region
                GROUP BY region_id, year, month
            )
            SELECT
                b.region_id,
                b.year,
                b.month,
                b.brand_id,
                b.rooms_sold,
                b.room_revenue,
                (b.rooms_sold::NUMERIC / NULLIF(t.total_rooms, 0) * 100)::NUMERIC(6,2),
                (b.room_revenue / NULLIF(t.total_revenue, 0) * 100)::NUMERIC(6,2)
            FROM brand_region b
            JOIN totals t ON t.region_id = b.region_id AND t.year = b.year AND t.month = b.month;

            INSERT INTO agg_sentiment_trends
            SELECT
                hotel_id,
                d.year,
                d.month,
                topic,
                COUNT(*)::INTEGER AS review_count,
                AVG(score)::NUMERIC(5,2) AS avg_score,
                AVG(sentiment)::NUMERIC(5,2) AS avg_sentiment,
                COUNT(*) FILTER (WHERE score <= 2)::INTEGER AS detractor_count,
                COUNT(*) FILTER (WHERE score >= 4)::INTEGER AS promoter_count
            FROM fact_guest_reviews gr
            JOIN dim_date d ON d.id = gr.date_id
            GROUP BY hotel_id, d.year, d.month, topic;

            INSERT INTO agg_channel_performance
            SELECT
                b.hotel_id,
                d.year,
                d.month,
                b.channel_id,
                COUNT(*)::INTEGER AS bookings,
                SUM(b.rooms_booked * b.length_of_stay)::INTEGER AS room_nights,
                SUM(b.gross_room_revenue)::NUMERIC(14,2) AS gross_revenue,
                SUM(b.commission_amount)::NUMERIC(14,2) AS commission_amount,
                SUM(b.net_room_revenue)::NUMERIC(14,2) AS net_revenue,
                (COUNT(*) FILTER (WHERE b.status = 'Cancelled')::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC(5,2) AS cancellation_rate
            FROM fact_bookings b
            JOIN dim_date d ON d.id = b.stay_date_id
            GROUP BY b.hotel_id, d.year, d.month, b.channel_id;

            INSERT INTO agg_seasonal_patterns
            SELECT
                h.region_id,
                d.month,
                d.day_of_week,
                AVG(k.occupancy_rate)::NUMERIC(5,2) AS avg_occupancy_rate,
                AVG(k.adr)::NUMERIC(10,2) AS avg_adr,
                AVG(k.revpar)::NUMERIC(10,2) AS avg_revpar,
                (AVG(k.rooms_sold)::NUMERIC / NULLIF(AVG(k.rooms_available), 0) * 100)::NUMERIC(6,2) AS demand_index
            FROM agg_daily_hotel_kpis k
            JOIN dim_date d ON d.id = k.date_id
            JOIN dim_hotel h ON h.id = k.hotel_id
            GROUP BY h.region_id, d.month, d.day_of_week;

            UPDATE hotels h
            SET
                occupancy_rate = s.occupancy_rate,
                revpar = s.revpar,
                avg_sentiment = COALESCE(s.avg_sentiment, h.avg_sentiment)
            FROM (
                SELECT
                    hotel_id,
                    AVG(occupancy_rate)::NUMERIC(5,2) AS occupancy_rate,
                    AVG(revpar)::NUMERIC(10,2) AS revpar,
                    AVG(avg_sentiment)::NUMERIC(5,2) AS avg_sentiment
                FROM agg_daily_hotel_kpis
                GROUP BY hotel_id
            ) s
            WHERE h.id = s.hotel_id;
            """,
    )


async def seed_management_reporting_layer(conn) -> None:
    """Create USALI-style management reporting tables and report-ready marts."""
    await execute_script(
        conn,
        """
        DROP TABLE IF EXISTS
            rpt_quarterly_business_review,
            rpt_monthly_owner_pack,
            rpt_weekly_pace,
            rpt_daily_flash,
            rpt_capex_tracker,
            rpt_guest_satisfaction_index,
            rpt_usali_monthly_pl,
            fact_capex_projects,
            fact_food_beverage_outlets,
            fact_labor_costs,
            fact_budget_targets,
            dim_brand_standard,
            bridge_hotel_comp_set,
            dim_usali_account
        CASCADE;

        CREATE TABLE dim_usali_account (
            id SERIAL PRIMARY KEY,
            account_code VARCHAR(20) NOT NULL UNIQUE,
            account_name VARCHAR(150) NOT NULL,
            department VARCHAR(100) NOT NULL,
            statement_section VARCHAR(100) NOT NULL,
            is_revenue BOOLEAN NOT NULL,
            is_payroll BOOLEAN NOT NULL,
            sort_order INTEGER NOT NULL
        );

        CREATE TABLE bridge_hotel_comp_set (
            hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id) ON DELETE CASCADE,
            competitor_name VARCHAR(150) NOT NULL,
            market_position VARCHAR(50) NOT NULL,
            rooms INTEGER NOT NULL,
            star_rating INTEGER NOT NULL,
            fair_share NUMERIC(6,2) NOT NULL,
            effective_from DATE NOT NULL,
            effective_to DATE,
            PRIMARY KEY (hotel_id, competitor_name, effective_from)
        );

        CREATE TABLE dim_brand_standard (
            id SERIAL PRIMARY KEY,
            brand_id INTEGER NOT NULL REFERENCES dim_brand(id),
            standard_category VARCHAR(100) NOT NULL,
            standard_name VARCHAR(150) NOT NULL,
            required_score NUMERIC(5,2) NOT NULL,
            audit_frequency VARCHAR(50) NOT NULL,
            owner_role VARCHAR(100) NOT NULL
        );

        CREATE TABLE fact_budget_targets (
            id BIGSERIAL PRIMARY KEY,
            hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
            date_id INTEGER NOT NULL REFERENCES dim_date(id),
            budget_rooms_sold INTEGER NOT NULL,
            budget_adr NUMERIC(10,2) NOT NULL,
            budget_room_revenue NUMERIC(12,2) NOT NULL,
            budget_total_revenue NUMERIC(12,2) NOT NULL,
            budget_gop NUMERIC(12,2) NOT NULL,
            forecast_rooms_sold INTEGER NOT NULL,
            forecast_adr NUMERIC(10,2) NOT NULL,
            forecast_total_revenue NUMERIC(12,2) NOT NULL,
            UNIQUE (hotel_id, date_id)
        );

        CREATE TABLE fact_labor_costs (
            id BIGSERIAL PRIMARY KEY,
            hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
            date_id INTEGER NOT NULL REFERENCES dim_date(id),
            usali_account_id INTEGER NOT NULL REFERENCES dim_usali_account(id),
            department VARCHAR(100) NOT NULL,
            regular_hours NUMERIC(8,2) NOT NULL,
            overtime_hours NUMERIC(8,2) NOT NULL,
            wages NUMERIC(12,2) NOT NULL,
            benefits NUMERIC(12,2) NOT NULL,
            total_labor_cost NUMERIC(12,2) NOT NULL
        );

        CREATE TABLE fact_food_beverage_outlets (
            id BIGSERIAL PRIMARY KEY,
            hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
            date_id INTEGER NOT NULL REFERENCES dim_date(id),
            outlet_name VARCHAR(120) NOT NULL,
            meal_period VARCHAR(50) NOT NULL,
            covers INTEGER NOT NULL,
            average_check NUMERIC(10,2) NOT NULL,
            gross_revenue NUMERIC(12,2) NOT NULL,
            cost_of_sales NUMERIC(12,2) NOT NULL,
            net_revenue NUMERIC(12,2) NOT NULL
        );

        CREATE TABLE fact_capex_projects (
            id BIGSERIAL PRIMARY KEY,
            hotel_id INTEGER NOT NULL REFERENCES dim_hotel(id),
            project_name VARCHAR(160) NOT NULL,
            category VARCHAR(100) NOT NULL,
            approval_date_id INTEGER NOT NULL REFERENCES dim_date(id),
            planned_start_date_id INTEGER NOT NULL REFERENCES dim_date(id),
            planned_end_date_id INTEGER NOT NULL REFERENCES dim_date(id),
            status VARCHAR(50) NOT NULL,
            budget_amount NUMERIC(14,2) NOT NULL,
            committed_amount NUMERIC(14,2) NOT NULL,
            actual_spend NUMERIC(14,2) NOT NULL,
            expected_roi_percent NUMERIC(6,2) NOT NULL,
            guest_impact VARCHAR(100) NOT NULL,
            brand_mandated BOOLEAN NOT NULL
        );
        """,
    )

    await conn.execute(
        text(
            """
            INSERT INTO dim_usali_account (account_code, account_name, department, statement_section, is_revenue, is_payroll, sort_order)
            VALUES
                ('4000', 'Rooms Revenue', 'Rooms', 'Operating Revenue', true, false, 10),
                ('4100', 'Food Revenue', 'Food & Beverage', 'Operating Revenue', true, false, 20),
                ('4200', 'Beverage Revenue', 'Food & Beverage', 'Operating Revenue', true, false, 30),
                ('4300', 'Spa Revenue', 'Spa', 'Operating Revenue', true, false, 40),
                ('4400', 'Parking Revenue', 'Other Operated', 'Operating Revenue', true, false, 50),
                ('4500', 'Other Revenue', 'Other Operated', 'Operating Revenue', true, false, 60),
                ('5100', 'Rooms Payroll', 'Rooms', 'Departmental Expense', false, true, 110),
                ('5200', 'F&B Payroll', 'Food & Beverage', 'Departmental Expense', false, true, 120),
                ('5300', 'Spa Payroll', 'Spa', 'Departmental Expense', false, true, 130),
                ('6100', 'Administrative & General', 'Undistributed', 'Undistributed Expense', false, false, 210),
                ('6200', 'Sales & Marketing', 'Undistributed', 'Undistributed Expense', false, false, 220),
                ('6300', 'Property Operations & Maintenance', 'Undistributed', 'Undistributed Expense', false, false, 230),
                ('6400', 'Utilities', 'Undistributed', 'Undistributed Expense', false, false, 240),
                ('7100', 'Management Fees', 'Fixed Charges', 'Below GOP', false, false, 310),
                ('7200', 'Insurance', 'Fixed Charges', 'Below GOP', false, false, 320),
                ('7300', 'Property Taxes', 'Fixed Charges', 'Below GOP', false, false, 330),
                ('7400', 'FF&E Reserve', 'Owner Charges', 'Below GOP', false, false, 340)
            """
        )
    )

    await conn.execute(
        text(
            """
            INSERT INTO bridge_hotel_comp_set (hotel_id, competitor_name, market_position, rooms, star_rating, fair_share, effective_from, effective_to)
            SELECT
                h.id,
                c.competitor_name,
                c.market_position,
                GREATEST(70, (h.rooms * c.room_factor)::INTEGER),
                LEAST(5, GREATEST(3, h.star_rating + c.rating_delta)),
                (100.0 / 5)::NUMERIC(6,2),
                DATE '2024-01-01',
                NULL
            FROM dim_hotel h
            CROSS JOIN (
                VALUES
                    ('GlobalStay', 'Primary', 1.12, 0),
                    ('Premier Palace', 'Aspirational', 0.82, 1),
                    ('CityHub', 'Primary', 1.25, -1),
                    ('Traveler Inn', 'Value', 1.40, -1),
                    ('Elite Collection', 'Luxury', 0.72, 1)
            ) AS c(competitor_name, market_position, room_factor, rating_delta)
            """
        )
    )

    await conn.execute(
        text(
            """
            INSERT INTO dim_brand_standard (brand_id, standard_category, standard_name, required_score, audit_frequency, owner_role)
            SELECT
                b.id,
                s.standard_category,
                s.standard_name,
                s.required_score,
                s.audit_frequency,
                s.owner_role
            FROM dim_brand b
            CROSS JOIN (
                VALUES
                    ('Service', 'Arrival welcome completed within 90 seconds', 92.00, 'Monthly', 'Front Office Manager'),
                    ('Rooms', 'Guestroom cleanliness inspection score', 94.00, 'Weekly', 'Executive Housekeeper'),
                    ('F&B', 'Breakfast quality and replenishment', 88.00, 'Monthly', 'F&B Manager'),
                    ('Digital', 'Wi-Fi speed and reliability', 90.00, 'Quarterly', 'IT Manager'),
                    ('Safety', 'Life-safety and emergency readiness', 98.00, 'Quarterly', 'Chief Engineer'),
                    ('Loyalty', 'Elite member recognition compliance', 93.00, 'Monthly', 'Rooms Director')
            ) AS s(standard_category, standard_name, required_score, audit_frequency, owner_role)
            """
        )
    )

    await conn.execute(
        text(
            """
            INSERT INTO fact_budget_targets (
                hotel_id, date_id, budget_rooms_sold, budget_adr, budget_room_revenue,
                budget_total_revenue, budget_gop, forecast_rooms_sold, forecast_adr, forecast_total_revenue
            )
            SELECT
                k.hotel_id,
                k.date_id,
                GREATEST(1, (k.rooms_available * (0.67 + random() * 0.10))::INTEGER),
                (k.adr * (0.96 + random() * 0.08))::NUMERIC(10,2),
                (GREATEST(1, (k.rooms_available * (0.67 + random() * 0.10))::INTEGER) * k.adr * (0.96 + random() * 0.08))::NUMERIC(12,2),
                (k.total_revenue * (0.94 + random() * 0.12))::NUMERIC(12,2),
                (k.total_revenue * (0.28 + random() * 0.10))::NUMERIC(12,2),
                GREATEST(1, (k.rooms_sold * (0.96 + random() * 0.08))::INTEGER),
                (k.adr * (0.98 + random() * 0.05))::NUMERIC(10,2),
                (k.total_revenue * (0.97 + random() * 0.08))::NUMERIC(12,2)
            FROM agg_daily_hotel_kpis k
            """
        )
    )

    await conn.execute(
        text(
            """
            INSERT INTO fact_labor_costs (
                hotel_id, date_id, usali_account_id, department, regular_hours,
                overtime_hours, wages, benefits, total_labor_cost
            )
            SELECT
                s.hotel_id,
                s.date_id,
                a.id,
                s.department,
                GREATEST(0, s.scheduled_hours - s.overtime_hours)::NUMERIC(8,2),
                s.overtime_hours,
                (s.labor_cost * 0.78)::NUMERIC(12,2),
                (s.labor_cost * 0.22)::NUMERIC(12,2),
                s.labor_cost
            FROM operational_staff_schedules s
            JOIN dim_usali_account a ON a.account_code = CASE
                WHEN s.department IN ('Front Office', 'Housekeeping') THEN '5100'
                WHEN s.department = 'Food & Beverage' THEN '5200'
                WHEN s.department = 'Maintenance' THEN '6300'
                ELSE '6100'
            END
            """
        )
    )

    await conn.execute(
        text(
            """
            INSERT INTO fact_food_beverage_outlets (
                hotel_id, date_id, outlet_name, meal_period, covers, average_check,
                gross_revenue, cost_of_sales, net_revenue
            )
            SELECT
                r.hotel_id,
                r.date_id,
                outlet.outlet_name,
                outlet.meal_period,
                GREATEST(1, (o.rooms_sold * outlet.capture_rate)::INTEGER),
                (outlet.average_check * (0.92 + random() * 0.18))::NUMERIC(10,2),
                (GREATEST(1, (o.rooms_sold * outlet.capture_rate)::INTEGER) * outlet.average_check * (0.92 + random() * 0.18))::NUMERIC(12,2),
                (GREATEST(1, (o.rooms_sold * outlet.capture_rate)::INTEGER) * outlet.average_check * outlet.cost_rate)::NUMERIC(12,2),
                (GREATEST(1, (o.rooms_sold * outlet.capture_rate)::INTEGER) * outlet.average_check * (1 - outlet.cost_rate))::NUMERIC(12,2)
            FROM fact_revenue r
            JOIN fact_occupancy o ON o.hotel_id = r.hotel_id AND o.date_id = r.date_id
            CROSS JOIN (
                VALUES
                    ('Main Restaurant', 'Breakfast', 0.58, 24.00, 0.31),
                    ('Main Restaurant', 'Dinner', 0.22, 48.00, 0.34),
                    ('Lobby Bar', 'Evening', 0.18, 36.00, 0.28),
                    ('Room Service', 'All Day', 0.08, 42.00, 0.36)
            ) AS outlet(outlet_name, meal_period, capture_rate, average_check, cost_rate)
            WHERE r.food_beverage_revenue > 0
            """
        )
    )

    await conn.execute(
        text(
            """
            INSERT INTO fact_capex_projects (
                hotel_id, project_name, category, approval_date_id, planned_start_date_id,
                planned_end_date_id, status, budget_amount, committed_amount, actual_spend,
                expected_roi_percent, guest_impact, brand_mandated
            )
            SELECT
                h.id,
                p.project_name,
                p.category,
                p.approval_date_id,
                p.planned_start_date_id,
                p.planned_end_date_id,
                p.status,
                (h.rooms * p.cost_per_room)::NUMERIC(14,2),
                (h.rooms * p.cost_per_room * p.committed_factor)::NUMERIC(14,2),
                (h.rooms * p.cost_per_room * p.actual_factor)::NUMERIC(14,2),
                p.expected_roi_percent,
                p.guest_impact,
                p.brand_mandated
            FROM dim_hotel h
            CROSS JOIN (
                VALUES
                    (1, 'Guestroom soft goods refresh', 'Rooms Renovation', 20240115, 20240515, 20240915, 'In Progress', 1800.00, 0.82, 0.55, 7.50, 'Medium', true),
                    (2, 'Wi-Fi infrastructure upgrade', 'Technology', 20240210, 20240601, 20240815, 'Completed', 420.00, 1.00, 0.96, 5.20, 'Low', true),
                    (3, 'Lobby seating and lighting refresh', 'Public Areas', 20240305, 20240701, 20241015, 'Approved', 650.00, 0.35, 0.10, 4.30, 'Medium', false),
                    (4, 'Kitchen equipment replacement', 'F&B', 20240420, 20240801, 20241115, 'Planning', 520.00, 0.20, 0.00, 6.80, 'Low', false)
            ) AS p(seq, project_name, category, approval_date_id, planned_start_date_id, planned_end_date_id, status, cost_per_room, committed_factor, actual_factor, expected_roi_percent, guest_impact, brand_mandated)
            """
        )
    )

    await execute_script(
        conn,
        """
        CREATE TABLE rpt_usali_monthly_pl AS
        WITH monthly AS (
            SELECT
                h.id AS hotel_id,
                h.name AS hotel_name,
                b.name AS brand,
                r.city AS market,
                d.year,
                d.month,
                SUM(o.rooms_available) AS room_nights_available,
                SUM(o.rooms_sold) AS room_nights_sold,
                SUM(fr.room_revenue)::NUMERIC(14,2) AS rooms_revenue,
                SUM(fr.food_beverage_revenue)::NUMERIC(14,2) AS food_beverage_revenue,
                SUM(fr.spa_revenue)::NUMERIC(14,2) AS spa_revenue,
                SUM(fr.parking_revenue + fr.other_revenue)::NUMERIC(14,2) AS other_operated_revenue,
                SUM(fr.total_revenue)::NUMERIC(14,2) AS total_revenue,
                SUM(l.total_labor_cost)::NUMERIC(14,2) AS labor_cost,
                SUM(fr.food_beverage_revenue * 0.31)::NUMERIC(14,2) AS fnb_cost_of_sales,
                SUM(fr.total_revenue * 0.075)::NUMERIC(14,2) AS admin_general,
                SUM(fr.total_revenue * 0.062)::NUMERIC(14,2) AS sales_marketing,
                SUM(fr.total_revenue * 0.048)::NUMERIC(14,2) AS property_ops_maintenance,
                SUM(fr.total_revenue * 0.041)::NUMERIC(14,2) AS utilities,
                SUM(fr.total_revenue * 0.030)::NUMERIC(14,2) AS management_fees,
                SUM(fr.total_revenue * 0.040)::NUMERIC(14,2) AS ffe_reserve
            FROM fact_revenue fr
            JOIN fact_occupancy o ON o.hotel_id = fr.hotel_id AND o.date_id = fr.date_id
            JOIN dim_date d ON d.id = fr.date_id
            JOIN dim_hotel h ON h.id = fr.hotel_id
            JOIN dim_brand b ON b.id = h.brand_id
            JOIN dim_region r ON r.id = h.region_id
            LEFT JOIN fact_labor_costs l ON l.hotel_id = fr.hotel_id AND l.date_id = fr.date_id
            GROUP BY h.id, h.name, b.name, r.city, d.year, d.month
        )
        SELECT
            *,
            (room_nights_sold::NUMERIC / NULLIF(room_nights_available, 0) * 100)::NUMERIC(5,2) AS occupancy_rate,
            (rooms_revenue / NULLIF(room_nights_sold, 0))::NUMERIC(10,2) AS adr,
            (rooms_revenue / NULLIF(room_nights_available, 0))::NUMERIC(10,2) AS revpar,
            (total_revenue - labor_cost - fnb_cost_of_sales - admin_general - sales_marketing - property_ops_maintenance - utilities)::NUMERIC(14,2) AS gop,
            ((total_revenue - labor_cost - fnb_cost_of_sales - admin_general - sales_marketing - property_ops_maintenance - utilities) / NULLIF(total_revenue, 0) * 100)::NUMERIC(6,2) AS gop_margin,
            (total_revenue - labor_cost - fnb_cost_of_sales - admin_general - sales_marketing - property_ops_maintenance - utilities - management_fees - ffe_reserve)::NUMERIC(14,2) AS noi
        FROM monthly;

        CREATE TABLE rpt_guest_satisfaction_index AS
        SELECT
            h.id AS hotel_id,
            h.name AS hotel_name,
            b.name AS brand,
            r.city AS market,
            d.year,
            d.month,
            COUNT(gr.id)::INTEGER AS review_count,
            AVG(gr.score)::NUMERIC(5,2) AS avg_review_score,
            AVG(gr.sentiment)::NUMERIC(5,2) AS sentiment_index,
            (COUNT(*) FILTER (WHERE gr.score >= 4)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC(6,2) AS promoter_rate,
            (COUNT(*) FILTER (WHERE gr.score <= 2)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC(6,2) AS detractor_rate,
            (AVG(gr.sentiment) * 100)::NUMERIC(6,2) AS gss_score,
            RANK() OVER (PARTITION BY r.city, d.year, d.month ORDER BY AVG(gr.sentiment) DESC) AS market_gss_rank
        FROM fact_guest_reviews gr
        JOIN dim_date d ON d.id = gr.date_id
        JOIN dim_hotel h ON h.id = gr.hotel_id
        JOIN dim_brand b ON b.id = h.brand_id
        JOIN dim_region r ON r.id = h.region_id
        GROUP BY h.id, h.name, b.name, r.city, d.year, d.month;

        CREATE TABLE rpt_capex_tracker AS
        SELECT
            h.id AS hotel_id,
            h.name AS hotel_name,
            b.name AS brand,
            r.city AS market,
            p.project_name,
            p.category,
            p.status,
            p.budget_amount,
            p.committed_amount,
            p.actual_spend,
            (p.actual_spend - p.budget_amount)::NUMERIC(14,2) AS budget_variance,
            (p.actual_spend / NULLIF(p.budget_amount, 0) * 100)::NUMERIC(6,2) AS budget_utilization_percent,
            p.expected_roi_percent,
            p.guest_impact,
            p.brand_mandated
        FROM fact_capex_projects p
        JOIN dim_hotel h ON h.id = p.hotel_id
        JOIN dim_brand b ON b.id = h.brand_id
        JOIN dim_region r ON r.id = h.region_id;

        CREATE TABLE rpt_daily_flash AS
        SELECT
            h.id AS hotel_id,
            h.name AS hotel_name,
            b.name AS brand,
            r.city AS market,
            d.calendar_date,
            k.rooms_available,
            k.rooms_sold,
            k.occupancy_rate,
            k.adr,
            k.revpar,
            k.total_revenue,
            bt.budget_rooms_sold,
            bt.budget_adr,
            bt.budget_total_revenue,
            (k.rooms_sold - bt.budget_rooms_sold) AS rooms_sold_vs_budget,
            (k.adr - bt.budget_adr)::NUMERIC(10,2) AS adr_vs_budget,
            (k.total_revenue - bt.budget_total_revenue)::NUMERIC(12,2) AS revenue_vs_budget,
            pl.gop,
            pl.gop_margin,
            g.gss_score,
            g.market_gss_rank
        FROM agg_daily_hotel_kpis k
        JOIN dim_date d ON d.id = k.date_id
        JOIN dim_hotel h ON h.id = k.hotel_id
        JOIN dim_brand b ON b.id = h.brand_id
        JOIN dim_region r ON r.id = h.region_id
        JOIN fact_budget_targets bt ON bt.hotel_id = k.hotel_id AND bt.date_id = k.date_id
        LEFT JOIN rpt_usali_monthly_pl pl ON pl.hotel_id = h.id AND pl.year = d.year AND pl.month = d.month
        LEFT JOIN rpt_guest_satisfaction_index g ON g.hotel_id = h.id AND g.year = d.year AND g.month = d.month;

        CREATE TABLE rpt_weekly_pace AS
        WITH current_year AS (
            SELECT
                b.hotel_id,
                d.year,
                d.week_of_year,
                SUM(b.rooms_booked * b.length_of_stay) AS room_nights_on_books,
                SUM(b.net_room_revenue) AS revenue_on_books,
                AVG(b.adr) AS adr_on_books,
                AVG((b.stay_date_id::TEXT::DATE - b.booking_date_id::TEXT::DATE)) AS avg_booking_window_days
            FROM fact_bookings b
            JOIN dim_date d ON d.id = b.stay_date_id
            WHERE b.status = 'Stayed'
            GROUP BY b.hotel_id, d.year, d.week_of_year
        ), last_year AS (
            SELECT
                hotel_id,
                year + 1 AS year,
                week_of_year,
                room_nights_on_books AS ly_room_nights,
                revenue_on_books AS ly_revenue
            FROM current_year
        )
        SELECT
            h.id AS hotel_id,
            h.name AS hotel_name,
            br.name AS brand,
            r.city AS market,
            cy.year,
            cy.week_of_year,
            cy.room_nights_on_books::INTEGER,
            cy.revenue_on_books::NUMERIC(14,2),
            cy.adr_on_books::NUMERIC(10,2),
            cy.avg_booking_window_days::NUMERIC(6,2),
            COALESCE(ly.ly_room_nights, 0)::INTEGER AS ly_room_nights,
            COALESCE(ly.ly_revenue, 0)::NUMERIC(14,2) AS ly_revenue,
            (cy.room_nights_on_books - COALESCE(ly.ly_room_nights, 0))::INTEGER AS room_night_pickup_vs_ly,
            (cy.revenue_on_books - COALESCE(ly.ly_revenue, 0))::NUMERIC(14,2) AS revenue_pickup_vs_ly
        FROM current_year cy
        JOIN dim_hotel h ON h.id = cy.hotel_id
        JOIN dim_brand br ON br.id = h.brand_id
        JOIN dim_region r ON r.id = h.region_id
        LEFT JOIN last_year ly ON ly.hotel_id = cy.hotel_id AND ly.year = cy.year AND ly.week_of_year = cy.week_of_year;

        CREATE TABLE rpt_monthly_owner_pack AS
        SELECT
            pl.*,
            (pl.total_revenue - bt.budget_total_revenue)::NUMERIC(14,2) AS revenue_vs_budget,
            (pl.gop - bt.budget_gop)::NUMERIC(14,2) AS gop_vs_budget,
            g.gss_score,
            g.market_gss_rank,
            capex.open_capex_budget,
            capex.open_capex_spend
        FROM rpt_usali_monthly_pl pl
        LEFT JOIN (
            SELECT
                hotel_id,
                d.year,
                d.month,
                SUM(budget_total_revenue)::NUMERIC(14,2) AS budget_total_revenue,
                SUM(budget_gop)::NUMERIC(14,2) AS budget_gop
            FROM fact_budget_targets bt
            JOIN dim_date d ON d.id = bt.date_id
            GROUP BY hotel_id, d.year, d.month
        ) bt ON bt.hotel_id = pl.hotel_id AND bt.year = pl.year AND bt.month = pl.month
        LEFT JOIN rpt_guest_satisfaction_index g ON g.hotel_id = pl.hotel_id AND g.year = pl.year AND g.month = pl.month
        LEFT JOIN (
            SELECT
                hotel_id,
                SUM(budget_amount) FILTER (WHERE status IN ('Approved', 'In Progress', 'Planning'))::NUMERIC(14,2) AS open_capex_budget,
                SUM(actual_spend) FILTER (WHERE status IN ('Approved', 'In Progress', 'Planning'))::NUMERIC(14,2) AS open_capex_spend
            FROM fact_capex_projects
            GROUP BY hotel_id
        ) capex ON capex.hotel_id = pl.hotel_id;

        CREATE TABLE rpt_quarterly_business_review AS
        SELECT
            brand,
            market,
            year,
            ((month - 1) / 3 + 1)::INTEGER AS quarter,
            COUNT(DISTINCT hotel_id)::INTEGER AS hotel_count,
            SUM(room_nights_available)::INTEGER AS room_nights_available,
            SUM(room_nights_sold)::INTEGER AS room_nights_sold,
            (SUM(room_nights_sold)::NUMERIC / NULLIF(SUM(room_nights_available), 0) * 100)::NUMERIC(5,2) AS occupancy_rate,
            (SUM(rooms_revenue) / NULLIF(SUM(room_nights_sold), 0))::NUMERIC(10,2) AS adr,
            (SUM(rooms_revenue) / NULLIF(SUM(room_nights_available), 0))::NUMERIC(10,2) AS revpar,
            SUM(total_revenue)::NUMERIC(14,2) AS total_revenue,
            SUM(gop)::NUMERIC(14,2) AS gop,
            (SUM(gop) / NULLIF(SUM(total_revenue), 0) * 100)::NUMERIC(6,2) AS gop_margin,
            AVG(gss_score)::NUMERIC(6,2) AS gss_score,
            SUM(open_capex_budget)::NUMERIC(14,2) AS open_capex_budget,
            SUM(open_capex_spend)::NUMERIC(14,2) AS open_capex_spend
        FROM rpt_monthly_owner_pack
        GROUP BY brand, market, year, ((month - 1) / 3 + 1);
        """,
    )


async def create_indexes(conn) -> None:
    """Create analytical indexes used by agents and reports."""
    await execute_script(
        conn,
        """
            CREATE INDEX idx_fact_bookings_hotel_stay_date ON fact_bookings(hotel_id, stay_date_id);
            CREATE INDEX idx_fact_bookings_channel ON fact_bookings(channel_id);
            CREATE INDEX idx_fact_bookings_segment ON fact_bookings(guest_segment_id);
            CREATE INDEX idx_fact_occupancy_hotel_date ON fact_occupancy(hotel_id, date_id);
            CREATE INDEX idx_fact_revenue_hotel_date ON fact_revenue(hotel_id, date_id);
            CREATE INDEX idx_fact_guest_reviews_hotel_date ON fact_guest_reviews(hotel_id, date_id);
            CREATE INDEX idx_fact_competitor_rates_hotel_date ON fact_competitor_rates(hotel_id, date_id);
            CREATE INDEX idx_agg_monthly_brand_year_month ON agg_monthly_brand_performance(year, month);
            CREATE INDEX idx_agg_channel_year_month ON agg_channel_performance(year, month);
            """,
    )


async def log_seed_summary(conn) -> None:
    """Log final table counts."""
    tables = [
        "dim_date",
        "dim_region",
        "dim_brand",
        "dim_hotel",
        "hotels",
        "guest_reviews",
        "fact_bookings",
        "fact_occupancy",
        "fact_revenue",
        "fact_guest_reviews",
        "fact_competitor_rates",
        "operational_staff_schedules",
        "operational_maintenance_logs",
        "agg_daily_hotel_kpis",
        "agg_monthly_brand_performance",
        "agg_regional_market_share",
        "agg_sentiment_trends",
        "agg_channel_performance",
        "agg_seasonal_patterns",
        "dim_usali_account",
        "bridge_hotel_comp_set",
        "dim_brand_standard",
        "fact_budget_targets",
        "fact_labor_costs",
        "fact_food_beverage_outlets",
        "fact_capex_projects",
        "rpt_daily_flash",
        "rpt_weekly_pace",
        "rpt_usali_monthly_pl",
        "rpt_monthly_owner_pack",
        "rpt_quarterly_business_review",
    ]
    counts = {}
    for table in tables:
        result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        counts[table] = result.scalar_one()
    logging.info("Seeded hotel data warehouse: %s", counts)


async def seed():
    """Seed a realistic hotel company analytical database."""
    random.seed(RANDOM_SEED)
    engine = create_async_engine(get_database_url())

    async with engine.begin() as conn:
        await create_schema(conn)
        lookups = await seed_dimensions(conn)
        await seed_hotels_and_scd(conn, lookups)
        await seed_facts(conn, lookups)
        await seed_aggregates(conn)
        await seed_management_reporting_layer(conn)
        await create_indexes(conn)
        await log_seed_summary(conn)

    await engine.dispose()
    logging.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(seed())
