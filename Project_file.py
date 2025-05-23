import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import requests
import matplotlib.image as mpimg
from scipy.ndimage import gaussian_filter

# Coordinates for New Delhi
CITY_LAT = 28.61
CITY_LON = 77.23

def get_hourly_forecast(lat, lon):
    url = (f"https://api.open-meteo.com/v1/forecast?"
           f"latitude={lat}&longitude={lon}"
           f"&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,precipitation,"
           f"cloudcover,relative_humidity_2m,pressure_msl"
           f"&timezone=auto")
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Failed to fetch weather data.")
    
    data = response.json()
    return (
        data['hourly']['temperature_2m'],
        data['hourly']['wind_speed_10m'],
        data['hourly']['wind_direction_10m'],
        data['hourly']['precipitation'],
        data['hourly']['cloudcover'],
        data['hourly']['relative_humidity_2m'],
        data['hourly']['pressure_msl']
    )

# Fetch forecast
forecast_temps, forecast_winds, forecast_wind_dirs, forecast_rains, forecast_clouds, forecast_humidity, forecast_pressure = get_hourly_forecast(CITY_LAT, CITY_LON)

# Simulation Parameters
length = 10000.0
nx, ny = 50, 50
dx = length / (nx - 1)
dy = length / (ny - 1)
dt = 10.0
total_time = 3600 * 6
nt = int(total_time / dt)
wind_scale = 0.5

# Initialize temperature field
u = np.ones((nx, ny)) * (forecast_temps[0] - 2)
cx, cy = nx // 2, ny // 2
u[cx-3:cx+3, cy-3:cy+3] = forecast_temps[0] + 2

# Mesh
x = np.linspace(0, length/1000, nx)
y = np.linspace(0, length/1000, ny)
X, Y = np.meshgrid(x, y)
step = 4
X_slice = X[::step, ::step]
Y_slice = Y[::step, ::step]

frames, wind_u_frames, wind_v_frames = [], [], []
wind_magnitude_frames = []
rain_frames, cloud_frames = [], []
humidity_list, pressure_list = [], []

for n in range(nt):
    t = n * dt
    hours = t / 3600.0
    idx = min(int(hours), len(forecast_temps) - 2)
    frac = hours % 1

    # Interpolate weather data
    temp_now = forecast_temps[idx] * (1-frac) + forecast_temps[idx+1] * frac
    wind_now = forecast_winds[idx] * (1-frac) + forecast_winds[idx+1] * frac
    wind_dir_now = forecast_wind_dirs[idx] * (1-frac) + forecast_wind_dirs[idx+1] * frac
    rain_now = forecast_rains[idx] * (1-frac) + forecast_rains[idx+1] * frac
    cloud_now = forecast_clouds[idx] * (1-frac) + forecast_clouds[idx+1] * frac
    humidity_now = forecast_humidity[idx] * (1-frac) + forecast_humidity[idx+1] * frac
    pressure_now = forecast_pressure[idx] * (1-frac) + forecast_pressure[idx+1] * frac

    u_new = u.copy()

    # Wind components
    wind_u_scalar = wind_scale * wind_now * np.cos(np.radians(wind_dir_now))
    wind_v_scalar = wind_scale * wind_now * np.sin(np.radians(wind_dir_now))

    wind_u_field = np.ones((nx, ny)) * wind_u_scalar
    wind_v_field = np.ones((nx, ny)) * wind_v_scalar
    wind_speed_field = np.sqrt(wind_u_field**2 + wind_v_field**2)

    # Dynamic diffusion coefficient
    alpha = 0.005 + 0.0001 * (temp_now - 15)

    for i in range(1, nx-1):
        for j in range(1, ny-1):
            advection_x = -wind_u_scalar * (u[i+1, j] - u[i-1, j]) / (2 * dx)
            advection_y = -wind_v_scalar * (u[i, j+1] - u[i, j-1]) / (2 * dy)
            diffusion = alpha * (
                (u[i+1, j] - 2*u[i, j] + u[i-1, j]) / dx**2 +
                (u[i, j+1] - 2*u[i, j] + u[i, j-1]) / dy**2
            )
            u_new[i, j] = u[i, j] + dt * (advection_x + advection_y + diffusion)

    # Apply smoothing to temperature field
    u_new = gaussian_filter(u_new, sigma=1.5)

    # Boundary conditions
    u_new[0, :] += 0.05 * (temp_now - u_new[0, :])
    u_new[-1, :] += 0.05 * (temp_now - u_new[-1, :])
    u_new[:, 0] += 0.05 * (temp_now - u_new[:, 0])
    u_new[:, -1] += 0.05 * (temp_now - u_new[:, -1])

    u = u_new.copy()

    if n % 5 == 0:
        frames.append(u.copy())
        wind_u_frames.append(wind_u_field)
        wind_v_frames.append(wind_v_field)
        wind_magnitude_frames.append(wind_speed_field)
        rain_frames.append(np.ones((nx, ny)) * rain_now)
        cloud_frames.append(np.ones((nx, ny)) * cloud_now)
        humidity_list.append(humidity_now)
        pressure_list.append(pressure_now / 1013.25)  # Convert to atm

# ---- Visualization ----
fig, axs = plt.subplots(2, 2, figsize=(14, 10))
ax1, ax2 = axs[0]
ax3, ax4 = axs[1]

# Temp & Wind subplot
ax1.set_title('Real Weather Simulation Over New Delhi')
ax1.set_xlabel('Distance X (km)')
ax1.set_ylabel('Distance Y (km)')
cax = ax1.imshow(frames[0], cmap='coolwarm', origin='lower', extent=[0, length/1000, 0, length/1000], alpha=0.8)
wind_u0 = wind_u_frames[0][::step, ::step]
wind_v0 = wind_v_frames[0][::step, ::step]
wind_magnitude0 = wind_magnitude_frames[0][::step, ::step]
quiver = ax1.quiver(X_slice, Y_slice, wind_u0, wind_v0, wind_magnitude0, cmap='viridis', clim=(0, np.max(wind_magnitude0)), scale=50)
cb_temp = fig.colorbar(cax, ax=ax1, shrink=0.7, label='Temperature (°C)')
cb_wind = fig.colorbar(quiver, ax=ax1, shrink=0.7, label='Wind Speed (m/s)')
sim_time_text = ax1.text(0.98, 0.02, '', transform=ax1.transAxes, fontsize=12, color='black', ha='right', va='bottom')

# Rain Plot
rain_img = ax2.imshow(rain_frames[0], cmap='Blues', origin='lower', extent=[0, length/1000, 0, length/1000])
ax2.set_title('Rainfall (mm)')
cb_rain = fig.colorbar(rain_img, ax=ax2, shrink=0.7)

# Cloud Plot
cloud_img = ax3.imshow(cloud_frames[0], cmap='Greys', origin='lower', extent=[0, length/1000, 0, length/1000])
ax3.set_title('Cloud Cover (%)')
cb_cloud = fig.colorbar(cloud_img, ax=ax3, shrink=0.7)

# Humidity and Pressure
humidity_text = ax4.text(0.5, 0.6, '', ha='center', va='center', fontsize=14)
pressure_text = ax4.text(0.5, 0.4, '', ha='center', va='center', fontsize=14)
ax4.axis('off')

# --- Update Function ---
def update(frame_idx):
    cax.set_data(frames[frame_idx])
    wind_u = wind_u_frames[frame_idx][::step, ::step]
    wind_v = wind_v_frames[frame_idx][::step, ::step]
    wind_mag = wind_magnitude_frames[frame_idx][::step, ::step]
    quiver.set_UVC(wind_u, wind_v, wind_mag)

    rain_img.set_data(rain_frames[frame_idx])
    cloud_img.set_data(cloud_frames[frame_idx])

    # Update time and text
    total_seconds = frame_idx * dt * 5
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    sim_time_text.set_text(f"Simulated Time: {hours:02d}:{minutes:02d}")

    humidity_text.set_text(f"Humidity: {humidity_list[frame_idx]:.1f}%")
    pressure_text.set_text(f"Pressure: {pressure_list[frame_idx]:.3f} atm")

    return cax, quiver, rain_img, cloud_img, sim_time_text, humidity_text, pressure_text

ani = animation.FuncAnimation(fig, update, frames=len(frames), interval=50, blit=False)

plt.tight_layout()
ani.save("weather_simulation.gif", writer="pillow", fps=10)
plt.show()
