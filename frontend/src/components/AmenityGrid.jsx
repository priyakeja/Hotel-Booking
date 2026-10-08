import Icon from './Icon'
import Reveal from './Reveal'

/** Homepage "Our Amenities" band — icons come from the CMS `Amenity.icon`. */
export function AmenityGrid({ amenities = [] }) {
  if (!amenities.length) return null

  return (
    <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
      {amenities.map((amenity, index) => (
        <Reveal key={amenity.id} variant="zoom" delay={index * 70}>
          <div className="amenity">
            <span className="amenity__icon">
              <Icon name={amenity.icon} size={24} />
            </span>
            <span className="amenity__name">{amenity.name}</span>
          </div>
        </Reveal>
      ))}
    </div>
  )
}

/** Trust strip below the hero (Best price guarantee, 24/7 support, ...). */
export function FeatureStrip({ features = [] }) {
  if (!features.length) return null

  return (
    <div className="grid grid--4">
      {features.map((feature, index) => (
        <Reveal key={feature.id} delay={index * 90}>
          <div className="feature">
            <span className="icon-tile">
              <Icon name={feature.icon} size={22} />
            </span>
            <div>
              <h3 className="feature__title">{feature.title}</h3>
              {feature.description ? <p className="feature__desc">{feature.description}</p> : null}
            </div>
          </div>
        </Reveal>
      ))}
    </div>
  )
}

export default AmenityGrid
