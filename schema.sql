-- ============================================================
--  Hotel Booking Database Schema
--  Disesuaikan dengan kondisi database aktual (per 25 Juni 2026)
-- ============================================================

CREATE DATABASE IF NOT EXISTS hotel_booking;
USE hotel_booking;

-- ------------------------------------------------------------
-- Tabel: provinces
-- Master data provinsi di Indonesia
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `provinces` (
  `province_id` VARCHAR(255) NOT NULL,
  `province`    VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`province_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: cities
-- Master data kota/kabupaten, berelasi ke provinces
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `cities` (
  `city_id`     VARCHAR(255) NOT NULL,
  `province_id` VARCHAR(255) DEFAULT NULL,
  `city_name`   VARCHAR(255) DEFAULT NULL,
  `type`        VARCHAR(255) DEFAULT NULL,
  `postal_code` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`city_id`),
  KEY `province_id` (`province_id`),
  CONSTRAINT `cities_ibfk_1` FOREIGN KEY (`province_id`)
    REFERENCES `provinces` (`province_id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: users
-- Akun pengguna, mendukung login lokal maupun Google OAuth
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`            INT           NOT NULL AUTO_INCREMENT,
  `username`      VARCHAR(50)   NOT NULL,
  `password_hash` VARCHAR(255)  DEFAULT NULL,          -- NULL jika login via Google
  `email`         VARCHAR(100)  NOT NULL,
  `phone`         VARCHAR(20)   DEFAULT NULL,
  `google_id`     VARCHAR(100)  DEFAULT NULL,
  `auth_provider` VARCHAR(50)   DEFAULT 'local',       -- 'local' | 'google'
  `role`          ENUM('customer','admin') DEFAULT 'customer',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username`  (`username`),
  UNIQUE KEY `email`     (`email`),
  UNIQUE KEY `google_id` (`google_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: hotels
-- Data hotel, province_id & city_id berelasi ke tabel master
-- (image_url DIHAPUS – gambar kini disimpan di tabel hotel_images)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `hotels` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `name`        VARCHAR(100) NOT NULL,
  `location`    VARCHAR(100) NOT NULL,               -- Alamat detail (jalan, RT/RW, dsb.)
  `description` TEXT         DEFAULT NULL,
  `rating`      DECIMAL(3,1) DEFAULT 0.0,
  `province_id` VARCHAR(255) DEFAULT NULL,
  `city_id`     VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: hotel_images
-- Multiple images per hotel (relasi One-to-Many)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `hotel_images` (
  `id`        INT          NOT NULL AUTO_INCREMENT,
  `hotel_id`  INT          NOT NULL,
  `image_url` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `hotel_id` (`hotel_id`),
  CONSTRAINT `hotel_images_ibfk_1` FOREIGN KEY (`hotel_id`)
    REFERENCES `hotels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: rooms
-- Data kamar, berelasi ke hotels
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `rooms` (
  `id`          INT             NOT NULL AUTO_INCREMENT,
  `hotel_id`    INT             NOT NULL,
  `room_number` VARCHAR(10)     NOT NULL,
  `room_type`   VARCHAR(50)     NOT NULL,
  `price`       DECIMAL(10, 2)  NOT NULL,
  PRIMARY KEY (`id`),
  KEY `hotel_id` (`hotel_id`),
  CONSTRAINT `rooms_ibfk_1` FOREIGN KEY (`hotel_id`)
    REFERENCES `hotels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: room_images
-- Multiple images per kamar (relasi One-to-Many)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `room_images` (
  `id`        INT          NOT NULL AUTO_INCREMENT,
  `room_id`   INT          NOT NULL,
  `image_url` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `room_id` (`room_id`),
  CONSTRAINT `room_images_ibfk_1` FOREIGN KEY (`room_id`)
    REFERENCES `rooms` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: bookings
-- Transaksi pemesanan kamar oleh pelanggan
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bookings` (
  `id`             INT          NOT NULL AUTO_INCREMENT,
  `user_id`        INT          NOT NULL,
  `room_id`        INT          NOT NULL,
  `guest_name`     VARCHAR(100) NOT NULL,
  `contact_number` VARCHAR(20)  NOT NULL,
  `check_in`       DATE         NOT NULL,
  `check_out`      DATE         NOT NULL,
  `payment_method` VARCHAR(50)  NOT NULL,
  `status`         ENUM('Pending','Booked','Cancelled') DEFAULT 'Pending',
  `created_at`     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  `cancel_reason`  TEXT         DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `room_id`  (`room_id`),
  CONSTRAINT `bookings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `bookings_ibfk_2` FOREIGN KEY (`room_id`) REFERENCES `rooms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: waiting_lists
-- Pelanggan yang bergabung ke daftar tunggu kamar penuh
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `waiting_lists` (
  `id`         INT      NOT NULL AUTO_INCREMENT,
  `user_id`    INT      NOT NULL,
  `room_id`    INT      NOT NULL,
  `check_in`   DATE     NOT NULL,
  `check_out`  DATE     NOT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `room_id`  (`room_id`),
  CONSTRAINT `waiting_lists_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `waiting_lists_ibfk_2` FOREIGN KEY (`room_id`) REFERENCES `rooms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabel: reviews
-- Ulasan pelanggan untuk hotel berdasarkan pesanan yang selesai
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `reviews` (
  `id`         INT      NOT NULL AUTO_INCREMENT,
  `hotel_id`   INT      NOT NULL,
  `user_id`    INT      NOT NULL,
  `booking_id` INT      NOT NULL,
  `rating`     INT      NOT NULL CHECK (rating >= 1 AND rating <= 5),
  `comment`    TEXT     DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `hotel_id` (`hotel_id`),
  KEY `user_id`  (`user_id`),
  KEY `booking_id` (`booking_id`),
  UNIQUE KEY `unique_booking_review` (`booking_id`),
  CONSTRAINT `reviews_ibfk_1` FOREIGN KEY (`hotel_id`) REFERENCES `hotels` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reviews_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reviews_ibfk_3` FOREIGN KEY (`booking_id`) REFERENCES `bookings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
