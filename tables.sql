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

CREATE TABLE proposals (
    id              BIGINT PRIMARY KEY,
    added_on        TIMESTAMP WITH TIME ZONE DEFAULT now(),
    vote_count      INT DEFAULT 0,     --Total # of votes
    author_emails   VARCHAR(254)[] DEFAULT '{}',
    voters          BIGINT[] DEFAULT '{}'
);


CREATE TABLE revisions (
    id                      BIGSERIAL PRIMARY KEY,
    public_id               BIGINT REFERENCES proposals,
    added_on                TIMESTAMP WITH TIME ZONE DEFAULT now(),
    title                   VARCHAR(254),
    category                VARCHAR(127),
    duration                VARCHAR(63),
    description             TEXT,
    audience                TEXT,
    python_level            VARCHAR(63),
    objectives              TEXT,
    abstract                TEXT,
    outline                 TEXT,
    additional_notes        TEXT,
    additional_requirements TEXT
);
CREATE INDEX idx_proposal_id ON revisions (public_id);

CREATE TABLE authors (
    id          BIGSERIAL PRIMARY KEY,
    email       VARCHAR(254),
    name        VARCHAR(254),
    revision    BIGINT REFERENCES revisions
);

CREATE OR REPLACE FUNCTION authors_change() RETURNS trigger AS
$$
BEGIN
    UPDATE proposals SET
    author_emails=ARRAY(SELECT lower(email) FROM authors 
                        WHERE revision=NEW.revision)
    WHERE id=(SELECT public_id FROM revisions WHERE id=NEW.revision);
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER authors_change_trigger AFTER INSERT OR UPDATE
    ON authors FOR EACH ROW EXECUTE PROCEDURE authors_change();

CREATE TABLE vote_reasons (
    id          BIGSERIAL PRIMARY KEY,
    description VARCHAR(127)
);

CREATE TABLE votes (
    id          BIGSERIAL PRIMARY KEY,

    magnitude   SMALLINT,
    sign        SMALLINT,

    voter       BIGINT REFERENCES users,
    proposal    BIGINT REFERENCES proposals,

    reason      VARCHAR(63),

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
)
