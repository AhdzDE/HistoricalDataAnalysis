# Historical Data Analysis workflow
Python workflow for analyzing historical hydrologic data from the California Data Exchanfe Center (CDEC) and the California Water Data Library (WDL)
## porpuse 
    this project processes historical stream gage data for discharge and stage measurements
        The script:
        -imports CDEC or WDL data
        -cleans in valid or missing data 
        -assigns observtions to water years
        -calculates annual statistics 
        -calculates selected percentiles
        -exports results to Excel
## Project Structure 
''' text
 -Historical Analysis
    -data
    -output
-.gitignore
-enviromental.yml
-historical_analysis.py
-README.md 