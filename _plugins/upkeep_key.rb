# =============================================================================
# upkeep_key.rb — a short, meaningless-looking name for one upkeep alert
# =============================================================================
# WHY THIS EXISTS
#
# The "Needs a human" panel on /admin-stats/ lets her set an alert aside once
# she has looked at it and decided it is fine as it stands. That decision is
# remembered in the browser, so each alert needs a name to remember it BY.
#
# The name has to have two properties, which pull in opposite directions:
#
#   1. It must stay the same build after build for as long as the alert is
#      saying the same thing — otherwise the alert she set aside on Tuesday
#      comes back on Wednesday and the button was worthless.
#
#   2. It must CHANGE the moment the specifics change — a new day trip with
#      no country, a different personal best left blank — because "I've seen
#      this" was only ever true of the thing she actually saw.
#
# So the name is built from the specifics themselves (see upkeep-data.html,
# where each check hands over its own fingerprint), and this filter reduces
# that to twelve hex characters.
#
# WHY IT IS HASHED RATHER THAN READABLE
#
# /admin-upkeep.json carries these names so the editor's banner can leave out
# the alerts she has already dealt with. Netlify serves that file to anyone
# who asks for the URL — a login can only be checked after the file has been
# sent — so everything in it is public. A readable key would put the country
# names and post titles this page keeps behind the login into a public file
# by the back door. A hash of them says nothing to a stranger and works just
# as well as a name, because nothing ever needs to read it back.
#
# Truncated to 12 characters: 48 bits, against a list that is a handful of
# entries long. A collision would mean two alerts sharing one dismissal, and
# it will not happen.
# =============================================================================

require "digest"

module Jekyll
  module UpkeepKeyFilter
    def upkeep_key(input)
      # Whitespace varies with how the Liquid that built the fingerprint was
      # indented, and indentation is not a change in meaning — squeeze it out
      # so reformatting a check doesn't silently un-dismiss its alert.
      text = input.to_s.gsub(/\s+/, " ").strip
      Digest::SHA256.hexdigest(text)[0, 12]
    end
  end
end

Liquid::Template.register_filter(Jekyll::UpkeepKeyFilter)
