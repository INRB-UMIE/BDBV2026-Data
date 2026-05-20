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

# Python
# Commenting this out for now will eventually add the darts pipeline processing here
#python = Sys.which("python3.10")
#python <- python[1L]
#system2(python, c("-m", "pip install -r requirements.txt"))



# ----------- 2. Where is the data coming from?  ---------------

# This paper: https://www.nature.com/articles/s41597-025-04487-x


# ----------- 3. To be added: processing with darts pipeline -------------------
# Rasters are processed using the darts pipeline: https://dart-pipeline.readthedocs.io/en/latest/
# This was previously done for
# another project, so we are migrating over the code. For now, we are taking the
# outputs from the processing from another project, making some minor adjustments, 
# and uploading the data

# -------------------- 4. Read in Current NCDF Files  --------------------------
# When we have the darts pipeline code up and running we will likely remove ncdf
# files from repo and just have csv. For now, we read in our current ncdf files
# from another project, subset to our interested timepoint (most recent) and convert
# to csv

# Read ncdf
ncdf_raw <- nc_open("data/gdp_pc/processed/COD-2022-gdp_pc.zs.nc")
names(ncdf_raw$var)
names(ncdf_raw$dim)

# Read healthzone shapefile
healthzone_shapefile <- st_read("data/shapefiles/DRC_Health_zones.shp")

# Socioeconomic Inequality
vals <- ncvar_get(ncdf_raw, "gdp_pc")
regions <- ncvar_get(ncdf_raw, "region")


gdp_pc_table <- data.frame(ZSCode = regions,
                           gdp_pc = vals)

joined_shapefile_gdp_pc <- healthzone_shapefile |>
  dplyr::left_join(gdp_pc)

p <- ggplot(joined_shapefile_gdp_pc) +
  geom_sf(aes(fill = gdp_pc), col = NA) +
  scale_fill_viridis_c(
    name = "GDP Per Capita",   # legend title
    option = "D"
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
  ggtitle("GDP Per Capita from Kummu et. al")

ggsave("data/gdp_pc/gdp_pc_processed_plot.png", p, height = 6, width = 6, units = "in")

final_export_gdp_pc <- joined_shapefile_gdp_pc |>
  dplyr::select(Nom, gdp_pc) |>
  dplyr::rename(nom = Nom) |>
  st_drop_geometry()

write.csv(final_export_gdp_pc, "data/gdp_pc/processed/gdp_pc__gdp_pc__static.csv")
