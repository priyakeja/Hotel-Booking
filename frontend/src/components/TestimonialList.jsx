import { initials } from '../utils/format'
import Icon from './Icon'
import Reveal from './Reveal'
import StarRating from './StarRating'

/** Guest quotes pulled from the CMS `Testimonial` model. */
export default function TestimonialList({ testimonials = [] }) {
  if (!testimonials.length) return null

  return (
    <div className="grid grid--3">
      {testimonials.map((testimonial, index) => (
        <Reveal key={testimonial.id} delay={index * 110}>
          <figure className="testimonial" style={{ margin: 0, height: '100%' }}>
            <Icon name="sparkles" size={20} className="gold-text" />
            <blockquote className="testimonial__quote">{testimonial.message}</blockquote>
            <StarRating value={testimonial.rating} showValue={false} />
            <figcaption className="testimonial__footer">
              {testimonial.image ? (
                <img className="testimonial__avatar" src={testimonial.image} alt="" loading="lazy" />
              ) : (
                <span className="testimonial__avatar testimonial__avatar--fallback">
                  {initials(testimonial.name)}
                </span>
              )}
              <span>
                <span className="testimonial__name" style={{ display: 'block' }}>
                  {testimonial.name}
                </span>
                {testimonial.location ? (
                  <span className="testimonial__location">{testimonial.location}</span>
                ) : null}
              </span>
            </figcaption>
          </figure>
        </Reveal>
      ))}
    </div>
  )
}
