-- ==========================================
-- Renvora AI Admin Database
-- Version: 1.0
-- ==========================================

CREATE TABLE IF NOT EXISTS admin (

    id INT AUTO_INCREMENT PRIMARY KEY,

    full_name VARCHAR(150) NOT NULL,

    username VARCHAR(100) UNIQUE NOT NULL,

    email VARCHAR(150) UNIQUE NOT NULL,

    password VARCHAR(255) NOT NULL,

    role ENUM('Super Admin','Admin','Manager')
    DEFAULT 'Admin',

    status ENUM('Active','Inactive')
    DEFAULT 'Active',

    last_login DATETIME NULL,

    created_at TIMESTAMP
    DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP
    DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP

);
INSERT INTO admin (

full_name,
username,
email,
password,
role

)

VALUES (

'Renvora Administrator',

'admin',

'admin@renvoratech.com',

'admin123',

'Super Admin'

);