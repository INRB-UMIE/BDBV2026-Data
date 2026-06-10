#!/usr/bin/env Rscript
# Convert INSP/DHIS2 province-level onset aggregates to BDBV2026-Data contract CSVs.
#
# Reads:
#   raw/province_aggregated.csv   columns: province, date_of_symptom_onset, total_positive
#
# Writes:
#   processed/aggregated_insp_linelist__confirmed_cases_onset__daily.csv
#   processed/aggregated_insp_linelist__national_confirmed_cases_onset__daily.csv
#
# Run from repo root:
#   Rscript data/aggregated_insp_linelist/process.R

args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg[1]), winslash = "/", mustWork = TRUE))
} else {
  normalizePath(getwd(), winslash = "/", mustWork = FALSE)
}

resolve_repo_root <- function() {
  from_script <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = FALSE)
  if (dir.exists(file.path(from_script, "data", "shapefiles"))) {
    return(from_script)
  }
  cwd <- normalizePath(getwd(), winslash = "/", mustWork = FALSE)
  if (dir.exists(file.path(cwd, "data", "shapefiles"))) {
    return(cwd)
  }
  stop("Could not locate repo root (expected data/shapefiles/)", call. = FALSE)
}

if (!requireNamespace("sf", quietly = TRUE)) {
  install.packages("sf", repos = "https://cloud.r-project.org")
}
suppressPackageStartupMessages(library(sf))

repo_root <- resolve_repo_root()
DATA_DIR <- file.path(repo_root, "data", "aggregated_insp_linelist")
RAW_CSV <- file.path(DATA_DIR, "raw", "province_aggregated.csv")
PROCESSED_DIR <- file.path(DATA_DIR, "processed")
PROVINCE_ALIASES_CSV <- file.path(repo_root, "data", "province_aliases.csv")
SHAPEFILE <- file.path(repo_root, "data", "shapefiles", "DRC_Health_zones.shp")

OUT_PROVINCE <- file.path(
  PROCESSED_DIR,
  "aggregated_insp_linelist__provincial_confirmed_cases_onset__daily.csv"
)
OUT_NATIONAL <- file.path(
  PROCESSED_DIR,
  "aggregated_insp_linelist__national_confirmed_cases_onset__daily.csv"
)

NATIONAL_ROLLUP_NOM <- "DRC"

INPUT_COL_PROVINCE <- "province"
INPUT_COL_DATE <- "date_of_symptom_onset"
INPUT_COL_COUNT <- "total_positive"

load_canonical_provinces <- function() {
  zones <- st_read(SHAPEFILE, quiet = TRUE)
  sort(unique(as.character(zones$PROVINCE)))
}

load_province_alias_index <- function(canonical_provinces) {
  if (!file.exists(PROVINCE_ALIASES_CSV)) {
    return(character())
  }
  aliases <- read.csv(PROVINCE_ALIASES_CSV, stringsAsFactors = FALSE, fileEncoding = "UTF-8-BOM")
  idx <- character()
  for (i in seq_len(nrow(aliases))) {
    observed <- trimws(aliases$observed_name[i])
    canonical <- trimws(aliases$canonical_province[i])
    if (nzchar(observed) && nzchar(canonical) && canonical %in% canonical_provinces) {
      idx[[observed]] <- canonical
    }
  }
  idx
}

to_canonical_province <- function(name, canonical_provinces, alias_index) {
  if (is.na(name) || !nzchar(trimws(name))) {
    return(NA_character_)
  }
  label <- trimws(name)
  if (label %in% canonical_provinces) {
    return(label)
  }
  if (label %in% names(alias_index)) {
    return(unname(alias_index[[label]]))
  }
  NA_character_
}

to_iso_date <- function(value) {
  if (inherits(value, "Date")) {
    if (length(value) != 1L || is.na(value)) {
      return(NA_character_)
    }
    return(format(value, "%Y-%m-%d"))
  }
  text <- trimws(as.character(if (is.null(value)) "" else value))
  if (!nzchar(text)) {
    return(NA_character_)
  }
  if (grepl("^\\d{4}-\\d{2}-\\d{2}$", text)) {
    return(text)
  }
  for (fmt in c("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y")) {
    parsed <- suppressWarnings(as.Date(text, format = fmt))
    if (!is.na(parsed)) {
      return(format(parsed, "%Y-%m-%d"))
    }
  }
  NA_character_
}

normalize_input_columns <- function(df) {
  names(df) <- tolower(trimws(names(df)))
  required <- c(
    INPUT_COL_PROVINCE,
    INPUT_COL_DATE,
    INPUT_COL_COUNT
  )
  missing <- setdiff(required, names(df))
  if (length(missing)) {
    stop(
      "Input missing required columns: ",
      paste(missing, collapse = ", "),
      call. = FALSE
    )
  }
  df
}

process_province_aggregated <- function(
    raw_path = RAW_CSV,
    out_province = OUT_PROVINCE,
    out_national = OUT_NATIONAL
) {
  if (!file.exists(raw_path)) {
    stop("Input not found: ", raw_path, call. = FALSE)
  }

  canonical_provinces <- load_canonical_provinces()
  alias_index <- load_province_alias_index(canonical_provinces)

  raw <- read.csv(raw_path, stringsAsFactors = FALSE, fileEncoding = "UTF-8-BOM")
  raw <- normalize_input_columns(raw)

  province_rows <- list()
  skipped_dates <- 0L
  skipped_negative <- 0L

  for (i in seq_len(nrow(raw))) {
    nom <- to_canonical_province(
      raw[[INPUT_COL_PROVINCE]][[i]],
      canonical_provinces = canonical_provinces,
      alias_index = alias_index
    )
    if (is.na(nom)) {
      stop(
        "Unresolved province: ",
        raw[[INPUT_COL_PROVINCE]][[i]],
        "\nAdd a row to data/province_aliases.csv or fix the input."
      )
    }

    date_iso <- to_iso_date(raw[[INPUT_COL_DATE]][[i]])
    if (is.na(date_iso)) {
      skipped_dates <- skipped_dates + 1L
      next
    }

    count <- suppressWarnings(as.integer(round(as.numeric(raw[[INPUT_COL_COUNT]][[i]]))))
    if (is.na(count)) {
      count <- 0L
    }
    if (count < 0L) {
      skipped_negative <- skipped_negative + 1L
      next
    }

    key <- paste(nom, date_iso, sep = "\t")
    if (is.null(province_rows[[key]])) {
      province_rows[[key]] <- list(nom = nom, date = date_iso, confirmed_cases_onset = 0L)
    }
    province_rows[[key]]$confirmed_cases_onset <-
      province_rows[[key]]$confirmed_cases_onset + count
  }

  if (!length(province_rows)) {
    stop("No valid rows after processing ", raw_path, call. = FALSE)
  }

  province_df <- do.call(
    rbind,
    lapply(province_rows, function(row) {
      data.frame(
        nom = row$nom,
        date = row$date,
        confirmed_cases_onset = row$confirmed_cases_onset,
        stringsAsFactors = FALSE
      )
    })
  )
  province_df <- province_df[order(province_df$date, province_df$nom), , drop = FALSE]

  dup <- duplicated(province_df[, c("nom", "date"), drop = FALSE])
  if (any(dup)) {
    stop("Duplicate (nom, date) rows remain after aggregation — check input.")
  }

  national_df <- aggregate(
    confirmed_cases_onset ~ date,
    data = province_df,
    FUN = sum
  )
  names(national_df)[2] <- "national_confirmed_cases_onset"
  national_df$nom <- NATIONAL_ROLLUP_NOM
  national_df <- national_df[, c("nom", "date", "national_confirmed_cases_onset"), drop = FALSE]
  national_df <- national_df[order(national_df$date), , drop = FALSE]

  dir.create(PROCESSED_DIR, recursive = TRUE, showWarnings = FALSE)
  write.csv(province_df, out_province, row.names = FALSE, quote = FALSE, fileEncoding = "UTF-8")
  write.csv(national_df, out_national, row.names = FALSE, quote = FALSE, fileEncoding = "UTF-8")

  message("Read:  ", raw_path, " (", nrow(raw), " rows)")
  if (skipped_dates > 0L) {
    message("WARNING: skipped ", skipped_dates, " row(s) with unparseable dates")
  }
  if (skipped_negative > 0L) {
    message("WARNING: skipped ", skipped_negative, " row(s) with negative counts")
  }
  message("Wrote: ", out_province, " (", nrow(province_df), " rows)")
  message("Wrote: ", out_national, " (", nrow(national_df), " rows)")
  message(
    "Provinces: ",
    paste(sort(unique(province_df$nom)), collapse = ", ")
  )

  invisible(list(province = province_df, national = national_df))
}

process_province_aggregated()
message("Done.")

