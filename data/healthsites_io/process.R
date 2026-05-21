rm(list = ls())

# -------------- 1. Check Necessary packages are Installed ---------------------
# R
if(!require("sf")) install.packages("sf")
if(!require("dplyr")) install.packages("dplyr")
if(!require("ncdf4")) install.packages("ncdf4")
if(!require("terra")) install.packages("terra")
if(!require("here")) install.packages("here") 
if(!require("ggplot2")) install.packages("ggplot2") 

library(sf)
library(dplyr)
library(ncdf4)
library(terra)
library(here)
library(ggplot2)

wd <- here()
setwd(wd)

# --------------------- 2. Load Healthsites.io shapefile -----------------------

healthsites_shapefile <- st_read("data/healthsites_io/raw/Democratic Republic of the Congo-node.shp") |>
  dplyr::filter(!amenity %in% c("pharmacy", "dentist", "school")) |>
  dplyr::filter(!healthcare %in% c("laboratory", "rehabilitation", "blood_donation",  "optometrist"))

remaining_amenities <- unique(healthsites_shapefile$amenity)
remaining_healthcares <- unique(healthsites_shapefile$healthcare)

write.table(remaining_amenities, "data/healthsites_io/raw/included_amenities.txt")
write.table(remaining_healthcares, "data/healthsites_io/raw/included_healthcare.txt")

st_write(healthsites_shapefile, "data/healthsites_io/raw/healthsites_raw_filtered.shp")

# ---------------------- 3. Process with MoH shapefile -------------------------

healthzone_shapefile <- st_read("data/shapefiles/DRC_Health_zones.shp") |>
  st_make_valid()

# Disambiguate Nom for zones whose name appears in more than one province
# (currently Bili and Lubunga), mirroring the Python schema contract.
nom_counts <- healthzone_shapefile |>
  dplyr::count(Nom) |>
  dplyr::filter(n > 1) |>
  dplyr::pull(Nom)
healthzone_shapefile <- healthzone_shapefile |>
  dplyr::mutate(Nom = dplyr::if_else(
    Nom %in% nom_counts,
    paste0(Nom, " (", PROVINCE, ")"),
    Nom
  )) 


healthzone_healthsite_counts <- healthzone_shapefile |>
  dplyr::mutate(healthsite_count = lengths(st_intersects(healthzone_shapefile, healthsites_shapefile)))

# -------------------- 4. Plot points and cloropleth  --------------------------
# Plot point data
p <- ggplot(healthzone_shapefile) +
  geom_sf(col = "lightgrey", aes(fill = PROVINCE), alpha = 0.2, show.legend = F) +
  scale_fill_discrete(palette = sample(terrain.colors(26))) +
  geom_sf(data = healthsites_shapefile, aes(col = amenity), size = 1)  +
  theme_classic() +
  theme(axis.line = element_blank(),
        axis.ticks = element_blank(),
        axis.text = element_blank()) +
  ggtitle("Point data on healthsites obtained from Healthsites.io", subtitle = "Different provinces indicated by fill colour")

ggsave("data/healthsites_io/raw_point_data_plot.png", p, height = 6, width = 7, units = "in")


# Read healthzone heatmap
p <- ggplot(dplyr::mutate(healthzone_healthsite_counts, healthsite_count = ifelse(healthsite_count == 0, NA, healthsite_count))) +
  geom_sf(col = NA, aes(fill = healthsite_count)) +
  scale_fill_viridis_c(
    name = "Number of Healthsites",   # legend title
    option = "D",
    na.value = "lightgrey"
  ) +
  theme_classic() +
  theme(axis.line = element_blank(),
        axis.ticks = element_blank(),
        axis.text = element_blank(),
        legend.position = "inside",
        legend.position.inside = c(0.25,0.15),
        legend.direction = "horizontal",
        legend.title.position = "top",
        legend.background = element_blank()) +
  ggtitle("Count of Healthsites per Healthzone", subtitle = "Grey = No healthsites in area according to Healthsites.io")

ggsave("data/healthsites_io/healthsite_count_data_plot.png", p, height = 6, width = 7, units = "in")

final_export_healthsite_count <- healthzone_healthsite_counts |>
  dplyr::select(Nom, healthsite_count) |>
  dplyr::rename(nom = Nom) |>
  st_drop_geometry()

write.csv(final_export_healthsite_count, "data/healthsites_io/processed/healthsites_io__healthsite_count__static.csv")

# Healthsite density
healthzone_healthsite_density <- healthzone_healthsite_counts |>
  dplyr::mutate(area = as.numeric(st_area(healthzone_healthsite_counts))/1e6) |>
  dplyr::mutate(healthsite_density = healthsite_count / area)


p <- ggplot(dplyr::mutate(healthzone_healthsite_density, healthsite_density = ifelse(healthsite_count == 0, NA, healthsite_density))) +
  geom_sf(col = NA, aes(fill = log(healthsite_density))) +
  scale_fill_viridis_c(
    name = "Healthsite Density (Num sites per km^2)",   # legend title
    option = "D",
    na.value = "lightgrey",
    breaks = log(c(0.1, 1, 10)),
    labels = c(0.1, 1, 10)
  ) +
  theme_classic() +
  theme(axis.line = element_blank(),
        axis.ticks = element_blank(),
        axis.text = element_blank(),
        legend.position = "inside",
        legend.position.inside = c(0.25,0.15),
        legend.direction = "horizontal",
        legend.title.position = "top",
        legend.background = element_blank()) +
  ggtitle("Healthsite density per Healthzone", subtitle = "Grey = No healthsites in area according to Healthsites.io")

ggsave("data/healthsites_io/healthsite_density_data_plot.png", p, height = 6, width = 7, units = "in")

final_export_healthsite_density <- healthzone_healthsite_density |>
  dplyr::select(Nom, healthsite_density) |>
  dplyr::rename(nom = Nom) |>
  st_drop_geometry()

write.csv(final_export_healthsite_density, "data/healthsites_io/processed/healthsites_io__healthsite_density__static.csv")

