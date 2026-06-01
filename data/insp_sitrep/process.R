# all coding for PDFs was manually performed and conducted by a human researcher


# in order to correct for differences in the zone notation of the situation reports
# and the shapefile

# package install and run
rm(list = ls())

if (!requireNamespace("sf", quietly = TRUE)) {
  install.packages("sf")
}
if (!requireNamespace("here", quietly = TRUE)) {
  install.packages("here")
}

# load necessary libraries
library(sf)
library(here)

repo_root <- here::here()
setwd(repo_root)

DATA_DIR <- file.path(repo_root, "data", "insp_sitrep")
PROCESSED_DIR <- file.path(DATA_DIR, "processed")
SHAPEFILE <- file.path(repo_root, "data", "shapefiles", "DRC_Health_zones.shp")
ALIASES_CSV <- file.path(repo_root, "data", "aliases.csv")

# Not MoH health zones; kept in CSV nom but excluded from GeoJSON build.
NON_GEOGRAPHIC_NOMS <- c("Sans Fiche", "NA")
# National roll-up in national_* CSVs (one row per date; broadcast in GeoJSON build).
NATIONAL_ROLLUP_NOM <- "DRC"


# nom per shapefile dictionary
build_canonical_nom_lookup <- function(zones) {
  nom_counts <- table(zones$Nom)
  canonical <- ifelse(
    nom_counts[zones$Nom] > 1,
    paste0(zones$Nom, " (", zones$PROVINCE, ")"),
    zones$Nom
  )
  stats::setNames(canonical, zones$Nom)
}


# targets existing in shapefile
load_alias_index <- function(path, canonical_noms) {
  if (!file.exists(path)) {
    return(character())
  }
  aliases <- read.csv(path, stringsAsFactors = FALSE, fileEncoding = "UTF-8")
  idx <- character()
  for (i in seq_len(nrow(aliases))) {
    observed <- trimws(aliases$observed_name[i])
    canonical <- trimws(aliases$canonical_nom[i])
    if (nzchar(observed) && nzchar(canonical) && canonical %in% canonical_noms) {
      idx[[observed]] <- canonical
    }
  }
  idx
}


# resolve sitrep names if unknown
to_canonical <- function(name, canonical_noms, alias_index) {
  if (is.na(name) || !nzchar(trimws(name))) {
    return(NA_character_)
  }
  name <- trimws(name)
  if (name %in% NON_GEOGRAPHIC_NOMS || name == NATIONAL_ROLLUP_NOM) {
    return(name)
  }
  if (name %in% canonical_noms) {
    return(name)
  }
  if (name %in% names(alias_index)) {
    return(unname(alias_index[[name]]))
  }
  NA_character_
}


to_iso_date <- function(s) {
  s <- trimws(s)
  if (!nzchar(s)) {
    return(s)
  }
  if (grepl("^\\d{4}-\\d{2}-\\d{2}$", s)) {
    return(s)
  }
  for (fmt in c("%d/%m/%Y", "%m/%d/%y", "%m/%d/%Y", "%d/%m/%y")) {
    parsed <- as.Date(s, format = fmt)
    if (!is.na(parsed)) {
      return(format(parsed, "%Y-%m-%d"))
    }
  }
  stop("Unparseable date: ", s, " (use ISO YYYY-MM-DD)")
}


normalize_date_column <- function(df) {
  if (!"date" %in% names(df)) {
    return(df)
  }
  df$date <- vapply(df$date, to_iso_date, FUN.VALUE = character(1))
  df
}


normalize_nom_column <- function(df, canonical_noms, alias_index) {
  if (!"nom" %in% names(df)) {
    stop("CSV must contain a 'nom' column")
  }
  resolved <- vapply(
    df$nom,
    to_canonical,
    FUN.VALUE = character(1),
    canonical_noms = canonical_noms,
    alias_index = alias_index
  )
  allowed <- c(NON_GEOGRAPHIC_NOMS, NATIONAL_ROLLUP_NOM)
  unresolved <- sort(unique(df$nom[is.na(resolved) & !(df$nom %in% allowed)]))
  if (length(unresolved)) {
    stop(
      "Unresolved zone name(s): ",
      paste(unresolved, collapse = ", "),
      "\nAdd rows to data/aliases.csv or fix the CSV."
    )
  }
  df$nom <- resolved
  df
}


normalize_processed_csvs <- function(
    processed_dir = PROCESSED_DIR,
    canonical_noms,
    alias_index
) {
  files <- sort(list.files(
    processed_dir,
    pattern = "^insp_sitrep__.*__daily\\.csv$",
    full.names = TRUE
  ))
  if (!length(files)) {
    stop("No insp_sitrep__*__daily.csv files found in ", processed_dir)
  }

  message("Normalising ", length(files), " file(s) in ", processed_dir)

  for (path in files) {
    # Sitrep CSVs may carry a UTF-8 BOM from Excel exports.
    df <- read.csv(path, stringsAsFactors = FALSE, fileEncoding = "UTF-8-BOM")
    n_before <- nrow(df)
    df <- normalize_nom_column(df, canonical_noms, alias_index)
    df <- normalize_date_column(df)

    # Per-PoE rows share (nom, date); include PoE when present.
    key_cols <- intersect(c("nom", "date", "PoE"), names(df))
    dup <- duplicated(df[, key_cols, drop = FALSE])
    if (any(dup)) {
      stop(
        "Duplicate (nom, date) after canonicalisation in ",
        basename(path),
        " — merge rows manually before re-running."
      )
    }

    write.csv(df, path, row.names = FALSE, quote = FALSE, fileEncoding = "UTF-8")
    message("  OK: ", basename(path), " (", n_before, " rows)")
  }

  invisible(files)
}


# normalize and fix all zones
zones <- st_read(SHAPEFILE, quiet = TRUE)
per_feature <- build_canonical_nom_lookup(zones)
canonical_noms <- unique(unname(per_feature))
alias_index <- load_alias_index(ALIASES_CSV, canonical_noms)

message(
  "Loaded ", length(canonical_noms), " canonical zone names and ",
  length(alias_index), " alias(es) from ", ALIASES_CSV
)

normalize_processed_csvs(
  processed_dir = PROCESSED_DIR,
  canonical_noms = canonical_noms,
  alias_index = alias_index
)

message("Done.")
