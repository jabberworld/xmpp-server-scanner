CREATE TABLE pybot_servers (
	jid VARCHAR(255) NOT NULL UNIQUE,
	offline_since DATETIME DEFAULT NULL,
	times_queried_online INT UNSIGNED NOT NULL,
	times_queried INT UNSIGNED NOT NULL,
	PRIMARY KEY (jid)
) ENGINE=InnoDB CHARSET=utf8 COLLATE=utf8_bin;


CREATE TABLE pybot_service_types (
	category VARCHAR(255) NOT NULL,
	type VARCHAR(255) NOT NULL,
	PRIMARY KEY (category, type)
) ENGINE=InnoDB CHARSET=utf8 COLLATE=utf8_bin;


CREATE TABLE pybot_components (
	jid VARCHAR(255) NOT NULL,
	node VARCHAR(255) NULL,
	server_jid VARCHAR(255) NOT NULL,
	category VARCHAR(255) NOT NULL,
	type VARCHAR(255) NOT NULL,
	available BOOLEAN NOT NULL,
	-- Add ther server_jid due the service.localhost components
	PRIMARY KEY (jid, server_jid, category, type),
	FOREIGN KEY (server_jid) REFERENCES pybot_servers (jid)
	    ON DELETE CASCADE ON UPDATE CASCADE,
	FOREIGN KEY (category, type) REFERENCES pybot_service_types (category, type)
	    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB CHARSET=utf8 COLLATE=utf8_bin;
