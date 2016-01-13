CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(254) NOT NULL,
    display_name    VARCHAR(80),
    pw              VARCHAR(80),
    created_on      TIMESTAMP WITH TIME ZONE DEFAULT now(),
    approved_on     TIMESTAMP WITH TIME ZONE DEFAULT NULL
);
CREATE UNIQUE INDEX idx_users_email
    ON users (lower(email));

CREATE TABLE batchgroups (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(254),
    author_emails   VARCHAR(254)[],
    locked          BOOLEAN DEFAULT FALSE
);

CREATE TABLE proposals (
    id                      BIGINT PRIMARY KEY,
    updated                 TIMESTAMP WITH TIME ZONE DEFAULT now(),
    added_on                TIMESTAMP WITH TIME ZONE DEFAULT now(),
    vote_count              INT DEFAULT 0,     --Total # of votes
    voters                  BIGINT[] DEFAULT '{}',
    batchgroup              BIGINT REFERENCES batchgroups DEFAULT NULL,

    withdrawn               BOOLEAN DEFAULT FALSE,

    author_emails           VARCHAR(254)[],
    author_names            VARCHAR(254)[],
    title                   VARCHAR(254),
    category                VARCHAR(127),
    duration                VARCHAR(63),
    description             TEXT,
    audience                TEXT,
    audience_level          VARCHAR(63),
    objective               TEXT,
    abstract                TEXT,
    outline                 TEXT,
    notes                   TEXT,
    additional_requirements TEXT,
    recording_release       BOOLEAN,
    accepted                BOOLEAN DEFAULT NULL
);

DROP AGGREGATE IF EXISTS email_aggregate(VARCHAR(254)[]);
CREATE AGGREGATE email_aggregate (basetype = VARCHAR(254)[],
                                    sfunc = array_cat,
                                    stype = VARCHAR(254)[], initcond = '{}');

CREATE OR REPLACE FUNCTION batch_change() RETURNS trigger AS
$$
BEGIN 
    UPDATE batchgroups SET
    author_emails=(SELECT email_aggregate(author_emails)
                    FROM proposals WHERE batchgroup = NEW.batchgroup)
    WHERE id = NEW.batchgroup;
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

CREATE TRIGGER batch_change_trigger AFTER INSERT OR UPDATE
    ON proposals FOR EACH ROW EXECUTE PROCEDURE batch_change();

CREATE TABLE batchvotes (
    batchgroup      BIGINT REFERENCES batchgroups,
    voter           BIGINT REFERENCES users,
    accept          BIGINT[],
    created_on      TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_on      TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(voter, batchgroup)

);

CREATE TABLE bookmarks (
    voter       BIGINT,
    proposal    BIGINT,
    UNIQUE (voter, proposal)
);

CREATE TABLE standards (
    id          BIGSERIAL PRIMARY KEY,
    description VARCHAR(127)
);

CREATE TABLE votes (
    id          BIGSERIAL PRIMARY KEY,

    scores      JSON,

    voter       BIGINT REFERENCES users,
    proposal    BIGINT REFERENCES proposals,

    nominate    BOOLEAN DEFAULT FALSE,

    updated_on  TIMESTAMP WITH TIME ZONE DEFAULT now(),
    added_on    TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE (voter, proposal)
);

CREATE OR REPLACE FUNCTION votes_change() RETURNS trigger AS
$$
BEGIN 
    UPDATE proposals SET 
        vote_count=(SELECT count(*) FROM votes WHERE proposal=NEW.proposal),
        voters = ARRAY(SELECT voter FROM votes WHERE proposal=NEW.proposal)
        WHERE id=NEW.proposal;
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

CREATE TRIGGER votes_change_trigger AFTER INSERT OR UPDATE
    ON votes FOR EACH ROW EXECUTE PROCEDURE votes_change();

CREATE TABLE discussion (
    id          BIGSERIAL PRIMARY KEY,

    name        VARCHAR(254) DEFAULT NULL, --Author feedback force
    frm         BIGINT REFERENCES users,
    proposal    BIGINT REFERENCES proposals,
    created     TIMESTAMP WITH TIME ZONE DEFAULT now(),
    body        TEXT,
    feedback    BOOLEAN DEFAULT FALSE
);

CREATE TABLE unread (
    proposal    BIGINT REFERENCES proposals,
    voter       BIGINT REFERENCES users,
    PRIMARY KEY (proposal, voter)
);

CREATE TABLE batchmessages (
    id          BIGSERIAL PRIMARY KEY,

    frm         BIGINT REFERENCES users,
    batch       BIGINT REFERENCES batchgroups,
    body        TEXT,
    created     TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE batchunread (
    batch   BIGINT REFERENCES batchgroups,
    voter       BIGINT REFERENCES users,
    PRIMARY KEY (batch, voter)
);
