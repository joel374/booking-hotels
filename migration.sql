-- ============================================================
-- SQL Migration / ALTER Query
-- Untuk memperbarui database hotel_booking yang sudah berjalan
-- agar sesuai dengan spesifikasi skema terbaru di schema.sql
-- ============================================================

USE hotel_booking;

-- ------------------------------------------------------------
-- 1. Create Tabel Reviews (Mengatasi Error Table doesn't exist)
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

-- ------------------------------------------------------------
-- 2. Create Tabel Waiting Lists (Fitur Antrean Kamar Penuh)
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
-- 3. ALTER TABLE (Untuk Menambahkan Kolom Baru pada Tabel Existing)
-- ------------------------------------------------------------
ALTER TABLE `users` ADD COLUMN `last_login` DATETIME DEFAULT NULL;
ALTER TABLE `users` ADD COLUMN `google_id` VARCHAR(100) DEFAULT NULL;
ALTER TABLE `users` ADD COLUMN `auth_provider` VARCHAR(50) DEFAULT 'local';
ALTER TABLE `users` ADD COLUMN `full_name` VARCHAR(100) DEFAULT NULL;
ALTER TABLE `users` ADD COLUMN `photo_url` VARCHAR(255) DEFAULT NULL;
ALTER TABLE `users` ADD COLUMN `password_reset_token` VARCHAR(255) DEFAULT NULL;
ALTER TABLE `users` ADD COLUMN `password_reset_expires` DATETIME DEFAULT NULL;
ALTER TABLE `bookings` ADD COLUMN `cancel_reason` TEXT DEFAULT NULL;
ALTER TABLE `hotels` ADD COLUMN `is_deleted` TINYINT(1) DEFAULT 0;
ALTER TABLE `rooms` ADD COLUMN `is_deleted` TINYINT(1) DEFAULT 0;

-- ------------------------------------------------------------
-- 4. Create Tabel Audit Logs
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `admin_id`    INT          NOT NULL,
  `module`      VARCHAR(100) NOT NULL,
  `action`      VARCHAR(100) NOT NULL,
  `description` TEXT,
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `audit_logs_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
