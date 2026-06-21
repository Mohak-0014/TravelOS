"use client";

import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { ItineraryItemOut } from "@/lib/api";

// CSS dot marker for itinerary items
const dotIcon = L.divIcon({
  className: "",
  html: '<div style="width:12px;height:12px;background:#ff6b5c;border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:2px solid #ffffff;box-shadow:0 2px 6px rgba(20,34,61,0.35)"></div>',
  iconSize: [11, 11],
  iconAnchor: [5, 5],
  popupAnchor: [0, -8],
});

// Distinct star-shaped marker for the selected hotel
const hotelIcon = L.divIcon({
  className: "",
  html: '<div style="width:16px;height:16px;background:#f59e0b;border-radius:50%;border:2.5px solid #ffffff;box-shadow:0 2px 8px rgba(245,158,11,0.55);display:flex;align-items:center;justify-content:center;font-size:8px">🏨</div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  popupAnchor: [0, -10],
});

interface HotelPin {
  lat: number;
  lng: number;
  name: string;
}

interface Props {
  items: ItineraryItemOut[];
  centerLat: number;
  centerLng: number;
  hotel?: HotelPin | null;
  height?: string;
}

export default function TripMap({
  items,
  centerLat,
  centerLng,
  hotel,
  height = "300px",
}: Props) {
  return (
    <MapContainer
      center={[centerLat, centerLng]}
      zoom={13}
      scrollWheelZoom={false}
      style={{ height, width: "100%", borderRadius: "0" }}
    >
      <TileLayer
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {items.map((item) =>
        item.latitude != null && item.longitude != null ? (
          <Marker
            key={item.id}
            position={[item.latitude, item.longitude]}
            icon={dotIcon}
          >
            <Popup>
              <span className="text-sm font-medium">{item.title}</span>
              {item.address && (
                <p className="text-xs text-gray-500 mt-0.5">{item.address}</p>
              )}
            </Popup>
          </Marker>
        ) : null,
      )}

      {hotel && (
        <Marker position={[hotel.lat, hotel.lng]} icon={hotelIcon}>
          <Popup>
            <span className="text-sm font-semibold">🏨 {hotel.name}</span>
            <p className="text-xs text-gray-500 mt-0.5">Selected hotel</p>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}
