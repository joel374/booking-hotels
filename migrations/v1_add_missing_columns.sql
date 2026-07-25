-- 1. Add missing columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100) DEFAULT NULL AFTER role;
ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255) DEFAULT NULL AFTER full_name;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login DATETIME DEFAULT NULL AFTER photo_url;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at DATETIME DEFAULT CURRENT_TIMESTAMP AFTER password_reset_expires;
ALTER TABLE users ADD COLUMN IF NOT EXISTS theme VARCHAR(20) DEFAULT 'light' AFTER created_at;
ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(20) DEFAULT 'id' AFTER theme;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_preference TINYINT(1) DEFAULT 1 AFTER language;

-- 2. Add is_deleted to hotels and rooms
ALTER TABLE hotels ADD COLUMN IF NOT EXISTS is_deleted TINYINT(1) DEFAULT 0 AFTER city_id;
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS is_deleted TINYINT(1) DEFAULT 0 AFTER price;

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
