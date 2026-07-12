import { useState } from 'react'
import axios from 'axios'
import { API_URL } from "../lib/api.js";

export default function useRoofEstimate() {
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const estimateRoof = async (coords) => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await axios.post(`${API_URL}/estimate`, {
        lat: coords.lat,
        lon: coords.lon,
      })
      setResult(response.data)
    } catch (err) {
      if (err.response) {
        setError(
          `Server error: ${err.response.data.detail || err.response.status}`
        )
      } else if (err.request) {
        setError('Cannot reach backend. Is the server running?')
      } else {
        setError(`Error: ${err.message}`)
      }
    } finally {
      setLoading(false)
    }
  }

  return { result, setResult, loading, error, estimateRoof }
}
