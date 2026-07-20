# Visionary Eyes: Rooftop Segmentation for Solar Panel Installation

## Objective and Description
* The objective of this application is to develop an end-to-end deep learning solution that addresses a data-driven problem with significant social impact.
* Specifically, the system is designed to detect and estimate usable rooftop areas for solar panel installation using satellite image segmentation.
* This project operates within the Renewable Energy domain and utilizes Image data modalities.
* The project serves as a complete full-stack application, incorporating both deployed front-end and back-end components.
* The deep learning solution is fully deployed as a functional web application.

## Details on How to Use the Application
1. **Launch the Application:** Open your browser and navigate to the frontend web application interface.
2. **Locate Target Property:** Use the interactive map to drop a pin on the target residential building (or use the search functionality).
3. **Run Segmentation:** Click the "Estimate" button. The backend will process the satellite imagery using our fine-tuned segmentation models to detect the precise residential rooftop boundary.
4. **View Roof Metrics:** The application will return the segmented polygon and display the calculated usable rooftop area (in square meters). User can also correct the predicted mask.
5. **Calculate Solar ROI:** Navigate to the Solar Analysis tab, input the monthly electricity bill, and click calculate. The system will leverage the estimated roof area alongside NASA satellite weather data and AI loss models (L5/L7) to provide a comprehensive breakdown of generation, savings, and payback periods.
