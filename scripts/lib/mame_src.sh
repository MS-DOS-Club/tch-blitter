# shellcheck shell=bash
# mame_src.sh -- where the MAME checkout and its binaries are, and the commit it is pinned to.
# Sourced, never executed; the caller sets PROJECT_DIR first.
#
# The checkout is $MAME_SRC when set, else $PROJECT_DIR/upstream.

# The checkout is a second git repository, so git's own variables, set when a script runs from a
# git hook, would point its commands at this repository's index instead.
unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE

# The pin, written once: the commit everything is built and verified against.
MAME_PINNED_COMMIT="da9333a2a5123012a939e78c3f2df7175ea7d100"

# clone_pinned <repository url> <dest> -- a shallow checkout of exactly MAME_PINNED_COMMIT.
# `git clone --branch` takes a branch or a tag and never a SHA, so it is an init plus a fetch of
# that one commit; checking out FETCH_HEAD is what lands on the pin and not on some branch's tip.
# It is built beside the destination and moved in only once whole, as `git clone` would leave it:
# setup takes any `.git` at the destination for a finished clone and never retries it.
clone_pinned() {
    local partial="$2.partial"
    rm -rf "$partial"
    if git init -q "$partial" \
        && git -C "$partial" remote add origin "$1" \
        && git -C "$partial" fetch -q --depth 1 origin "$MAME_PINNED_COMMIT" \
        && git -C "$partial" checkout -q --detach FETCH_HEAD; then
        mv "$partial" "$2"
    else
        rm -rf "$partial"
        return 1
    fi
}

# pinned_commit_state <checkout> -- is that checkout AT MAME_PINNED_COMMIT? The version string is no
# witness: master keeps the last release's number after the pin moves, so `-version` reads healthy
# on a tree that is commits behind and that the patches then refuse. Prints the checkout's HEAD
# (or nothing when there is none) and answers: 0 at the pin, 1 elsewhere, 2 no git metadata, which is
# INVALID and never green.
pinned_commit_state() {
    local head
    [ -e "$1/.git" ] || return 2
    head=$(git -C "$1" rev-parse HEAD 2>/dev/null) || return 2
    printf "%s\n" "$head"
    [ "$head" = "$MAME_PINNED_COMMIT" ]
}

mame_src_path() { printf "%s\n" "${MAME_SRC:-$PROJECT_DIR/upstream}"; }
