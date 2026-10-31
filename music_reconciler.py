# /// script
# dependencies = [
#   "argparse",
#   "filecomp",
#   "pathlib",
#   "tinytag",
# ]
# ///

import argparse
from filecmp import cmp
from pathlib import Path
from shutil import copy
from typing import Optional

from tinytag import TinyTag

dry_run = True


def get_all_music_metadata(path: Path) -> list[TinyTag]:
    files = []

    def impl(path: Path):
        for entry in path.iterdir():
            if entry.is_file() and TinyTag.is_supported(entry):
                files.append(TinyTag.get(entry))
            elif entry.is_dir():
                impl(entry)

    impl(path)
    return files


def compare_tracks(lhs: TinyTag, rhs: TinyTag) -> bool:
    lhs_title = replace_non_ascii(lhs.title.lower())
    lhs_artist = replace_non_ascii(lhs.artist.lower())
    lhs_album = replace_non_ascii(lhs.album.lower())
    rhs_title = replace_non_ascii(rhs.title.lower())
    rhs_artist = replace_non_ascii(rhs.artist.lower())
    rhs_album = replace_non_ascii(rhs.album.lower())
    return (
        lhs_title == rhs_title and lhs_artist == rhs_artist and lhs_album == rhs_album
    )


def get_all_duplicates(tags: list[TinyTag]) -> list[list[TinyTag]]:
    dupes_list = []
    for i in range(len(tags)):
        matches = [tags[i]]
        for j in range(i + 1, len(tags)):
            if compare_tracks(tags[i], tags[j]):
                matches.append(tags[j])

        if len(matches) > 1:
            dupes_list.append(matches)

    return dupes_list


def get_all_update_conflicts(tags: list[TinyTag], update: TinyTag) -> list[TinyTag]:
    matches = [update]
    for i in range(len(tags)):
        if compare_tracks(update, tags[i]) and not cmp(
            update.filename, tags[i].filename
        ):
            matches.append(tags[i])

    return matches


def get_conflict_selection(
    options: list[TinyTag],
) -> tuple[list[TinyTag], list[TinyTag]]:
    input_invalid = True
    selected_list = []

    print("Conflicts found!")
    for i, option in enumerate(options):
        print(f"    {i + 1}: {option.filename}")
    while input_invalid:
        print("Keep which of the following? Keep multiple with `#,#,#...`")
        selected = input()
        selected_list = selected.split(",")
        for i in range(len(selected_list)):
            selected_list[i] = selected_list[i].strip()
        for selected in selected_list:
            try:
                selected_num = int(selected)
                if selected_num <= 0 or selected_num > len(options):
                    print("Invalid selection!")
                    continue
                input_invalid = False
            except ValueError:
                print("Non-integer input!")
                continue

    print()

    keep_list = []
    deletion_list = []
    for i, option in enumerate(options):
        if str(i + 1) in selected_list:
            print(f"Keeping {option.filename}")
            keep_list.append(option)
            continue
        deletion_list.append(option)
    print()
    return keep_list, deletion_list


def prompt_for_deletion(deletion_list: list[TinyTag], update: Optional[TinyTag] = None):
    for delete in deletion_list:
        if update is not None and delete == update:
            continue

        print(f"Delete the following file? (Y/n) {delete.filename}")
        confirm = input()
        if len(confirm) < 1 or confirm[0] in ("y", "Y"):
            if not dry_run:
                print("Consider it done")
                Path(delete.filename).unlink()
        else:
            print("Skipped")
    print()


def prompt_for_copy(update: TinyTag, new_path: str):
    print(f"Copy {update.filename} to {new_path}? (Y/n)")
    confirm = input()
    if len(confirm) < 1 or confirm[0] in ("y", "Y"):
        if not dry_run:
            print("Consider it done")
            Path("/".join(new_path.split("/")[:-1])).mkdir(parents=True, exist_ok=True)
            copy(update.filename, new_path)
    else:
        print("Skipped")


def write_new_files(path: Path, update_list: list[TinyTag]):
    for update in update_list:
        resultant_path = (
            str(path)
            + "/"
            + replace_non_ascii(
                update.artist
                + "/"
                + update.album
                + "/"
                + f"{update.track:02d}"
                + "_"
                + update.title
                + "."
                + update.filename.split(".")[-1]
            )
        )
        if resultant_path == update.filename or (
            Path(resultant_path).is_file() and cmp(resultant_path, update.filename)
        ):
            continue
        prompt_for_copy(update, resultant_path)


def prompt_for_dedupe(dupes: list[TinyTag]):
    if len(dupes) < 1:
        return

    _, deletion_list = get_conflict_selection(dupes)
    prompt_for_deletion(deletion_list)


def replace_non_ascii(filename: str) -> str:
    return (
        filename.replace(" ", "_")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
        .replace("‒", "-")
        .replace("*", "_")
        .replace(":", "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("?", "_")
        .replace("|", "_")
        .replace('"', "_")
    )


def prompt_for_update(path: Path, update: TinyTag, options: list[TinyTag]):
    if len(options) < 1:
        return

    if len(options) > 1:
        update_list, deletion_list = get_conflict_selection(options)
        prompt_for_deletion(deletion_list, update)

    else:
        update_list = options

    write_new_files(path, update_list)


def deduplicate(path: Path):
    files = get_all_music_metadata(path)
    dupes = get_all_duplicates(files)
    for dupe in dupes:
        prompt_for_dedupe(dupe)


def update(path: Path, update_file: Path):
    files = get_all_music_metadata(path)
    updates = []
    if update_file.is_dir():
        updates = get_all_music_metadata(update_file)
    else:
        updates.append(TinyTag.get(update_file))

    for update in updates:
        options = get_all_update_conflicts(files, update)
        prompt_for_update(path, update, options)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--deduplicate", action="store_true", help="Delete duplciate files."
    )
    parser.add_argument(
        "-u", "--update", type=str, help="Update library with the provided file."
    )
    parser.add_argument(
        "-dr",
        "--dry-run",
        action="store_true",
        help="Dry run. Don't make any filesystem changes.",
    )
    parser.add_argument("path", help="Path to music library")
    args = parser.parse_args()

    global dry_run
    dry_run = args.dry_run

    if args.deduplicate:
        deduplicate(Path(args.path))

    if args.update:
        update(Path(args.path), Path(args.update))


if __name__ == "__main__":
    main()
