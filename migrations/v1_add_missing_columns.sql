-- 1. Add missing columns to users table
ALTER TABLE users ADD COLUMN full_name VARCHAR(100) DEFAULT NULL AFTER role;
ALTER TABLE users ADD COLUMN photo_url VARCHAR(255) DEFAULT NULL AFTER full_name;
ALTER TABLE users ADD COLUMN last_login DATETIME DEFAULT NULL AFTER photo_url;
ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP AFTER password_reset_expires;
ALTER TABLE users ADD COLUMN theme VARCHAR(20) DEFAULT 'light' AFTER created_at;
ALTER TABLE users ADD COLUMN language VARCHAR(20) DEFAULT 'id' AFTER theme;
ALTER TABLE users ADD COLUMN notification_preference VARCHAR(50) DEFAULT 'all' AFTER language;

-- 2. Add is_deleted to hotels and rooms
ALTER TABLE hotels ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER city_id;
ALTER TABLE rooms ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER price;

-- 3. Add notifications table
CREATE TABLE IF NOT EXISTS `notifications` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `title`       VARCHAR(100) NOT NULL,
  `description` TEXT         NOT NULL,
  `icon_type`   VARCHAR(50)  DEFAULT 'info',
  `is_read`     TINYINT(1)   DEFAULT 0,
  `created_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
